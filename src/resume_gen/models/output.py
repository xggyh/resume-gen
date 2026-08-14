"""Output resume + provenance + reports.

OutputResume is the single source of truth fed into all renderers
(HTML/PDF/DOCX/Markdown).
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field

from .resume import BasicInfo, Education, Publication, Talk, Award, Certification


class OutputBullet(BaseModel):
    """A rewritten bullet with provenance back to original bullet(s)."""
    text: str
    source_ids: list[str] = Field(
        default_factory=list,
        description="IDs of original Bullet(s) this was rewritten from. Empty list means hallucinated and will be flagged.",
    )
    matched_requirements: list[str] = Field(
        default_factory=list,
        description="IDs of JDRequirement(s) this bullet addresses.",
    )
    keywords_used: list[str] = Field(default_factory=list)


class OutputSubSection(BaseModel):
    """A labelled sub-block within one Experience entry.

    Use when one role spans several distinct workstreams that deserve
    their own emphasis (e.g. an algo lead working on multiple products).
    """
    title: str
    date_range: Optional[str] = Field(None, description="e.g. '2024-03 – 2025-01' or '2025-06 – Present'")
    summary_line: Optional[str] = Field(None, description="Optional one-line italic context under the sub-section title, before bullets.")
    bullets: list[OutputBullet] = Field(default_factory=list)


class OutputExperience(BaseModel):
    source_id: str = Field(description="Original Experience.id")
    company: str
    role: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    summary_line: Optional[str] = Field(
        None,
        description="Optional one-line italic summary under the role heading, before bullets/sub-sections.",
    )
    bullets: list[OutputBullet] = Field(
        default_factory=list,
        description="Flat bullets (ignored if sub_sections is non-empty).",
    )
    sub_sections: list[OutputSubSection] = Field(default_factory=list)


class OutputProject(BaseModel):
    source_id: str
    name: str
    role: Optional[str] = None
    organization: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    tech_stack: list[str] = Field(default_factory=list)
    bullets: list[OutputBullet] = Field(default_factory=list)
    link: Optional[str] = None


class OutputResume(BaseModel):
    basic_info: BasicInfo
    professional_summary: str
    professional_summary_bullets: list[str] = Field(
        default_factory=list,
        description="If non-empty, the summary section renders as bullets instead of a paragraph.",
    )
    core_skills: list[str] = Field(default_factory=list, description="Curated, JD-aligned skill chips")
    skills_groups: dict[str, list[str]] = Field(
        default_factory=dict,
        description="If non-empty, skills section renders one labelled row per group (e.g. 'LLM / GenAI': [...]).",
    )
    experiences: list[OutputExperience] = Field(default_factory=list)
    projects: list[OutputProject] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    talks: list[Talk] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    section_order: list[str] = Field(
        default_factory=lambda: [
            "summary", "experience", "projects", "education",
            "publications", "talks", "awards", "certifications", "skills",
        ],
        description=(
            "Order in which sections appear in the rendered resume. Skills "
            "is placed last by default; templates honour this order."
        ),
    )
    section_labels: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional section-heading overrides keyed by canonical section "
            "name (e.g. 'summary' -> '个人简介'). Missing keys fall back to "
            "the renderer's English default."
        ),
    )

    target_role_title: Optional[str] = None
    target_company: Optional[str] = None


# ---- Reports ---------------------------------------------------------------


class RequirementCoverage(BaseModel):
    requirement_id: str
    requirement_text: str
    importance: Literal["required", "preferred", "nice_to_have"]
    coverage: Literal["strong", "partial", "missing"]
    evidence: list[str] = Field(default_factory=list, description="Quoted output bullets that cover this requirement")


class MatchReport(BaseModel):
    role_title: str
    keywords_total: int
    keywords_covered: int
    keyword_coverage_pct: float
    requirements: list[RequirementCoverage]
    required_missing: list[str] = Field(default_factory=list, description="Required JDRequirement ids not covered")


class RewriteRecord(BaseModel):
    """Per-bullet trace of what changed."""
    output_text: str
    source_ids: list[str]
    source_texts: list[str] = Field(default_factory=list)
    rewrite_type: Literal["verbatim", "rephrased", "consolidated", "emphasized", "generated_summary"]


class RiskReport(BaseModel):
    rewrites: list[RewriteRecord] = Field(default_factory=list)
    unsupported_bullets: list[str] = Field(default_factory=list, description="Output bullets without traceable source — should be reviewed")
    uncovered_requirements: list[str] = Field(default_factory=list, description="JD requirements with no evidence in original resume")
    notes: list[str] = Field(default_factory=list)


# ---- Aggregate -------------------------------------------------------------


class PipelineArtifacts(BaseModel):
    """All intermediate artifacts produced by a single run, for debugging and replay."""
    resume_raw_text: str
    jd_raw_text: str
    resume_data: dict  # ResumeData serialized
    jd_matrix: dict  # JDMatrix serialized
    relevance: dict   # bullet_id -> {score, matched_req_ids}
    output_resume: dict  # OutputResume serialized
    match_report: dict
    risk_report: dict
