"""Generate the Professional Summary aligned to JD."""

from __future__ import annotations

from datetime import date
import re
from pydantic import BaseModel

from ..llm import LLM
from ..llm.prompts import SUMMARY_SYSTEM, SUMMARY_USER_TEMPLATE, tone_for
from ..models import ResumeData, JDMatrix, OutputBullet


class _SummaryOut(BaseModel):
    summary: str


def _estimate_years_experience(resume: ResumeData) -> int:
    months_total = 0
    for exp in resume.experiences:
        s = _ym(exp.start_date)
        e = _ym(exp.end_date) or (date.today().year * 12 + date.today().month)
        if s and e and e >= s:
            months_total += (e - s)
    return max(0, months_total // 12)


def _ym(s):
    if not s:
        return None
    if isinstance(s, str) and s.lower() == "present":
        return date.today().year * 12 + date.today().month
    m = re.match(r"(\d{4})[-/]?(\d{1,2})?", s or "")
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else 6
    return y * 12 + max(1, min(12, mo))


def generate_summary(
    resume: ResumeData,
    jd: JDMatrix,
    selected_bullets: list[OutputBullet],
    llm: LLM,
) -> str:
    top_reqs = [
        f"- [{r.importance}] {r.text}"
        for r in jd.requirements
        if r.importance in {"required", "preferred"}
    ][:8]
    candidate_signal = "\n".join(f"- {b.text}" for b in selected_bullets[:8]) or "(no bullets selected)"

    out = llm.structured(
        schema=_SummaryOut,
        system=SUMMARY_SYSTEM,
        user=SUMMARY_USER_TEMPLATE.format(
            role_title=jd.role_title,
            company=jd.company or "(target company)",
            tone_profile=tone_for(jd.role_type),
            top_requirements="\n".join(top_reqs) or "(no JD requirements)",
            candidate_signal=candidate_signal,
            years_exp=_estimate_years_experience(resume),
        ),
        tool_name="emit_summary",
        tool_description="Emit the 3–4 sentence professional summary.",
        heavy=True,
        max_tokens=1024,
        temperature=0.4,
    )
    return out.summary.strip()
