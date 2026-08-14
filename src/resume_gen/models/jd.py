"""Structured JD representation — the 'capability matrix' we match against."""

from __future__ import annotations

import uuid
from typing import Literal, Optional
from pydantic import BaseModel, Field


Importance = Literal["required", "preferred", "nice_to_have"]
RoleType = Literal["research", "engineering", "solution_architect", "data_science", "ml_engineering", "product", "generalist"]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class JDRequirement(BaseModel):
    """One distilled capability/skill/responsibility from the JD."""
    id: str = Field(default_factory=lambda: _new_id("req"))
    text: str = Field(description="Concise capability statement, e.g. 'Designs distributed training pipelines'")
    category: Literal["hard_skill", "soft_skill", "responsibility", "domain", "bonus"]
    importance: Importance
    keywords: list[str] = Field(default_factory=list, description="Exact phrases worth carrying into the resume verbatim for ATS")


class JDMatrix(BaseModel):
    role_title: str
    company: Optional[str] = None
    role_type: RoleType = Field(description="Drives the rewriting tone profile")
    seniority: Optional[Literal["intern", "junior", "mid", "senior", "staff", "principal", "manager", "director"]] = None
    requirements: list[JDRequirement] = Field(default_factory=list)
    industry: Optional[str] = None
    location: Optional[str] = None
    language: Literal["en", "zh", "mixed"] = "en"

    def required(self) -> list[JDRequirement]:
        return [r for r in self.requirements if r.importance == "required"]

    def all_keywords(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for r in self.requirements:
            for kw in r.keywords:
                k = kw.strip()
                if k and k.lower() not in seen:
                    seen.add(k.lower())
                    out.append(k)
        return out
