"""Curate the Core Skills section."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm import LLM
from ..llm.prompts import SKILLS_SYSTEM, SKILLS_USER_TEMPLATE
from ..models import ResumeData, JDMatrix


class _SkillsOut(BaseModel):
    skills: list[str] = Field(default_factory=list)


def curate_core_skills(resume: ResumeData, jd: JDMatrix, llm: LLM) -> list[str]:
    declared = [s.name for s in resume.skills]
    evidenced: set[str] = set()
    for _, b in resume.all_bullets():
        for t in b.technologies:
            evidenced.add(t)
    for exp in resume.experiences:
        for t in exp.tech_stack:
            evidenced.add(t)
    for prj in resume.projects:
        for t in prj.tech_stack:
            evidenced.add(t)

    jd_block = "\n".join(
        f"- [{r.importance}] {r.text} | kw: {', '.join(r.keywords) or '-'}"
        for r in jd.requirements
        if r.category in {"hard_skill", "domain", "responsibility"}
    )[:3000]

    out = llm.structured(
        schema=_SkillsOut,
        system=SKILLS_SYSTEM,
        user=SKILLS_USER_TEMPLATE.format(
            jd_requirements=jd_block or "(none)",
            declared_skills=", ".join(sorted(set(declared))) or "(none declared)",
            evidenced_skills=", ".join(sorted(evidenced)) or "(none evidenced)",
        ),
        tool_name="emit_skills",
        tool_description="Emit 8–14 core skill strings.",
        heavy=False,
        max_tokens=1024,
        temperature=0.2,
    )

    # Trim and de-dupe while preserving order
    seen: set[str] = set()
    chips: list[str] = []
    for s in out.skills:
        k = s.strip()
        if not k:
            continue
        kl = k.lower()
        if kl in seen:
            continue
        seen.add(kl)
        chips.append(k)
        if len(chips) >= 14:
            break
    return chips
