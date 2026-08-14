"""Raw resume text → ResumeData."""

from __future__ import annotations

from ..ingestion.loader import LoadedDocument
from ..llm import LLM
from ..llm.prompts import RESUME_PARSE_SYSTEM, RESUME_PARSE_USER_TEMPLATE
from ..models import ResumeData


def parse_resume(doc: LoadedDocument, llm: LLM) -> ResumeData:
    # JSON shortcut: if user supplies a pre-structured resume, validate and use it.
    if doc.detected_format == "json" and doc.structured is not None:
        return ResumeData.model_validate(doc.structured)

    prompt = RESUME_PARSE_USER_TEMPLATE.format(resume_text=doc.raw_text)
    return llm.structured(
        schema=ResumeData,
        system=RESUME_PARSE_SYSTEM,
        user=prompt,
        tool_name="emit_resume",
        tool_description="Emit the structured ResumeData.",
        heavy=False,
        max_tokens=8192,
        temperature=0.0,
    )
