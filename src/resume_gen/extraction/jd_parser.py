"""Raw JD text → JDMatrix (capability matrix)."""

from __future__ import annotations

from ..ingestion.loader import LoadedDocument
from ..llm import LLM
from ..llm.prompts import JD_PARSE_SYSTEM, JD_PARSE_USER_TEMPLATE
from ..models import JDMatrix


def parse_jd(doc: LoadedDocument, llm: LLM) -> JDMatrix:
    if doc.detected_format == "json" and doc.structured is not None:
        return JDMatrix.model_validate(doc.structured)

    prompt = JD_PARSE_USER_TEMPLATE.format(jd_text=doc.raw_text)
    return llm.structured(
        schema=JDMatrix,
        system=JD_PARSE_SYSTEM,
        user=prompt,
        tool_name="emit_jd_matrix",
        tool_description="Emit the structured JDMatrix.",
        heavy=False,
        max_tokens=4096,
        temperature=0.0,
    )
