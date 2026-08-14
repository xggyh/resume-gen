"""Build the MatchReport (JD coverage analysis) and RiskReport (provenance/gaps)."""

from __future__ import annotations

from ..models import (
    OutputResume,
    JDMatrix,
    ResumeData,
    MatchReport,
    RequirementCoverage,
    RiskReport,
    RewriteRecord,
)
from ..quality.checks import QualityResult


def build_match_report(jd: JDMatrix, output: OutputResume, q: QualityResult) -> MatchReport:
    coverages: list[RequirementCoverage] = []
    for req in jd.requirements:
        coverages.append(
            RequirementCoverage(
                requirement_id=req.id,
                requirement_text=req.text,
                importance=req.importance,
                coverage=q.requirement_coverage.get(req.id, "missing"),  # type: ignore[arg-type]
                evidence=q.requirement_evidence.get(req.id, []),
            )
        )
    return MatchReport(
        role_title=jd.role_title,
        keywords_total=len(q.keywords_covered) + len(q.keywords_missing),
        keywords_covered=len(q.keywords_covered),
        keyword_coverage_pct=q.keyword_coverage_pct,
        requirements=coverages,
        required_missing=q.required_missing_ids,
    )


def build_risk_report(
    jd: JDMatrix,
    original: ResumeData,
    output: OutputResume,
    q: QualityResult,
) -> RiskReport:
    id_to_orig = {b.id: b for _, b in original.all_bullets()}

    records: list[RewriteRecord] = []
    all_output_bullets = [b for e in output.experiences for b in e.bullets] + \
                        [b for p in output.projects for b in p.bullets]
    for ob in all_output_bullets:
        source_texts = [id_to_orig[s].text for s in ob.source_ids if s in id_to_orig]
        if not source_texts:
            rtype = "generated_summary"
        elif len(source_texts) == 1 and source_texts[0].strip() == ob.text.strip():
            rtype = "verbatim"
        elif len(source_texts) > 1:
            rtype = "consolidated"
        else:
            rtype = "rephrased"
        records.append(
            RewriteRecord(
                output_text=ob.text,
                source_ids=ob.source_ids,
                source_texts=source_texts,
                rewrite_type=rtype,  # type: ignore[arg-type]
            )
        )

    uncovered = [
        f"[{r.importance}] {r.text}"
        for r in jd.requirements
        if q.requirement_coverage.get(r.id) == "missing"
    ]

    notes: list[str] = []
    if q.required_missing_ids:
        notes.append(
            f"{len(q.required_missing_ids)} REQUIRED JD requirement(s) lack supporting evidence — "
            "do not invent. Consider whether you want to mention them in the cover letter instead."
        )
    if q.unsupported_bullets:
        notes.append(
            f"{len(q.unsupported_bullets)} output bullet(s) could not be traced to a source. "
            "Manually verify before sending."
        )
    if q.bullet_warnings:
        notes.append(f"{len(q.bullet_warnings)} bullet quality warning(s) — see logs.")

    return RiskReport(
        rewrites=records,
        unsupported_bullets=q.unsupported_bullets,
        uncovered_requirements=uncovered,
        notes=notes,
    )
