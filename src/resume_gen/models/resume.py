"""Structured representation of the original resume.

Every line item gets a stable id so downstream stages can track provenance
when content is reordered, rewritten, or dropped.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional
from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Bullet(BaseModel):
    """One achievement/responsibility line from an experience or project."""
    id: str = Field(default_factory=lambda: _new_id("b"))
    text: str
    technologies: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list, description="Quantified outcomes pulled from text, e.g. '30% latency reduction'")


class Experience(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("exp"))
    company: str
    role: str
    location: Optional[str] = None
    start_date: Optional[str] = Field(None, description="ISO-ish date string, e.g. '2022-03'")
    end_date: Optional[str] = Field(None, description="ISO-ish date string or 'Present'")
    bullets: list[Bullet] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list, description="Business / problem domains, e.g. 'fraud detection', 'recsys'")


class Project(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("prj"))
    name: str
    role: Optional[str] = None
    organization: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: list[Bullet] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    link: Optional[str] = None


class Education(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("edu"))
    institution: str
    degree: str
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    category: Optional[str] = Field(None, description="e.g. 'Languages', 'ML', 'Cloud'")
    proficiency: Optional[Literal["beginner", "intermediate", "advanced", "expert"]] = None


class Publication(BaseModel):
    title: str
    venue: Optional[str] = None
    year: Optional[str] = None
    authors: Optional[str] = None
    link: Optional[str] = None


class Talk(BaseModel):
    title: str
    venue: Optional[str] = None
    year: Optional[str] = None
    audience: Optional[str] = None


class Award(BaseModel):
    title: str
    issuer: Optional[str] = None
    year: Optional[str] = None


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None


class BasicInfo(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None
    headline: Optional[str] = Field(None, description="e.g. 'Senior ML Engineer'")


class ResumeData(BaseModel):
    """Faithful structured snapshot of the candidate's original resume."""
    basic_info: BasicInfo
    summary: Optional[str] = None
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    talks: list[Talk] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    def all_bullets(self) -> list[tuple[str, Bullet]]:
        """Return (owner_id, bullet) pairs across experiences and projects."""
        out: list[tuple[str, Bullet]] = []
        for exp in self.experiences:
            for b in exp.bullets:
                out.append((exp.id, b))
        for prj in self.projects:
            for b in prj.bullets:
                out.append((prj.id, b))
        return out
