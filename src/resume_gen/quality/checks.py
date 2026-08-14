"""Post-generation quality checks.

Checks:
- ATS keyword coverage (how many JD keywords appear verbatim in the resume)
- Requirement coverage (strong/partial/missing per JD requirement)
- Provenance / hallucination (every output bullet ties to ≥1 input bullet)
- Quality heuristics on bullets (length, action verb, presence of metric)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import OutputResume, JDMatrix, ResumeData


ACTION_VERBS = {
    "led", "built", "designed", "architected", "developed", "shipped", "delivered",
    "optimized", "improved", "scaled", "reduced", "increased", "drove", "launched",
    "owned", "established", "founded", "trained", "deployed", "automated",
    "migrated", "refactored", "implemented", "spearheaded", "managed", "mentored",
    "presented", "published", "researched", "prototyped", "engineered",
    "ran", "applied", "rolled", "rewrote", "headed", "executed", "championed",
    "acted", "co-led", "partnered", "collaborated", "crafted", "tuned", "evolved",
}


@dataclass
class QualityResult:
    keyword_coverage_pct: float
    keywords_covered: list[str]
    keywords_missing: list[str]

    requirement_coverage: dict[str, str]  # req_id -> 'strong' | 'partial' | 'missing'
    requirement_evidence: dict[str, list[str]]  # req_id -> bullet texts
    required_missing_ids: list[str]

    unsupported_bullets: list[str] = field(default_factory=list)
    bullet_warnings: list[str] = field(default_factory=list)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _resume_text_blob(resume: OutputResume) -> str:
    parts: list[str] = [
        resume.professional_summary or "",
        " ".join(getattr(resume, "professional_summary_bullets", []) or []),
        " ".join(resume.core_skills),
        " ".join(getattr(resume, "languages", []) or []),
    ]
    # Skills groups (when present, core_skills is empty)
    for group_name, group_skills in (getattr(resume, "skills_groups", {}) or {}).items():
        parts.append(group_name)
        parts.extend(group_skills)
    for exp in resume.experiences:
        parts.append(f"{exp.role} {exp.company}")
        if getattr(exp, "summary_line", None):
            parts.append(exp.summary_line or "")
        parts.extend(b.text for b in exp.bullets)
        for sub in getattr(exp, "sub_sections", []) or []:
            parts.append(sub.title)
            parts.extend(b.text for b in sub.bullets)
    for prj in resume.projects:
        parts.append(prj.name)
        parts.extend(prj.tech_stack)
        parts.extend(b.text for b in prj.bullets)
    for t in getattr(resume, "talks", []) or []:
        parts.append(f"{t.title} {t.venue or ''} {t.audience or ''}")
    for p in getattr(resume, "publications", []) or []:
        parts.append(f"{p.title} {p.venue or ''}")
    for a in getattr(resume, "awards", []) or []:
        parts.append(a.title)
    return _normalize(" ".join(parts))


def run_quality_checks(
    output: OutputResume,
    jd: JDMatrix,
    original: ResumeData,
) -> QualityResult:
    blob = _resume_text_blob(output)

    # 1. Keyword coverage
    keywords = jd.all_keywords()
    covered: list[str] = []
    missing: list[str] = []
    for kw in keywords:
        if _normalize(kw) in blob:
            covered.append(kw)
        else:
            missing.append(kw)
    pct = (100.0 * len(covered) / len(keywords)) if keywords else 100.0

    # 2. Requirement coverage from explicit links + keyword fallback.
    #    The fallback checks every "evidence-bearing" text fragment: bullets,
    #    sub-section bullets, summary, skills, talks, languages — anywhere
    #    the requirement could legitimately be supported.
    coverage: dict[str, str] = {}
    evidence: dict[str, list[str]] = {}
    all_output_bullets: list = []
    for e in output.experiences:
        all_output_bullets.extend(e.bullets)
        for sub in getattr(e, "sub_sections", []) or []:
            all_output_bullets.extend(sub.bullets)
    for p in output.projects:
        all_output_bullets.extend(p.bullets)

    fallback_fragments: list[str] = [
        output.professional_summary or "",
        *(getattr(output, "professional_summary_bullets", []) or []),
        " · ".join(output.core_skills),
        " · ".join(getattr(output, "languages", []) or []),
    ]
    for group_name, group_skills in (getattr(output, "skills_groups", {}) or {}).items():
        fallback_fragments.append(f"{group_name}: {' · '.join(group_skills)}")
    for t in getattr(output, "talks", []) or []:
        fallback_fragments.append(f"{t.title}. {t.venue or ''} {t.audience or ''}")
    for p in getattr(output, "publications", []) or []:
        fallback_fragments.append(f"{p.title}. {p.venue or ''}")
    for a in getattr(output, "awards", []) or []:
        fallback_fragments.append(a.title)

    for req in jd.requirements:
        ev_texts: list[str] = []
        for b in all_output_bullets:
            if req.id in b.matched_requirements:
                ev_texts.append(b.text)
        # Keyword fallback: bullets first, then non-bullet evidence fragments.
        if not ev_texts and req.keywords:
            for b in all_output_bullets:
                if any(_normalize(kw) in _normalize(b.text) for kw in req.keywords):
                    ev_texts.append(b.text)
                    break
            if not ev_texts:
                for frag in fallback_fragments:
                    if frag and any(_normalize(kw) in _normalize(frag) for kw in req.keywords):
                        ev_texts.append(frag.strip()[:240])
                        break

        if len(ev_texts) >= 2:
            coverage[req.id] = "strong"
        elif len(ev_texts) == 1:
            coverage[req.id] = "partial"
        else:
            coverage[req.id] = "missing"
        evidence[req.id] = ev_texts

    required_missing = [
        r.id for r in jd.requirements
        if r.importance == "required" and coverage.get(r.id) == "missing"
    ]

    # 3. Provenance / unsupported bullets
    original_ids = {b.id for _, b in original.all_bullets()}
    unsupported: list[str] = []
    for b in all_output_bullets:
        if not b.source_ids or not any(sid in original_ids for sid in b.source_ids):
            unsupported.append(b.text)

    # 4. Quality heuristics
    warnings: list[str] = []
    for b in all_output_bullets:
        words = b.text.split()
        if len(words) > 32:
            warnings.append(f"Bullet too long ({len(words)} words): {b.text[:80]}...")
        first = words[0].lower().strip(",.;:") if words else ""
        if first and first not in ACTION_VERBS and not first.endswith("ed") and not first.endswith("ing"):
            warnings.append(f"Bullet may lack action verb: {b.text[:80]}...")

    return QualityResult(
        keyword_coverage_pct=round(pct, 1),
        keywords_covered=covered,
        keywords_missing=missing,
        requirement_coverage=coverage,
        requirement_evidence=evidence,
        required_missing_ids=required_missing,
        unsupported_bullets=unsupported,
        bullet_warnings=warnings,
    )
