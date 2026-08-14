"""Score every (bullet, requirement) pair, then aggregate per bullet and per experience.

Strategy:
- Single LLM call with the full bullets list + requirements list as context.
- Light model (sonnet) is plenty for classification; opus would be overkill.
- We ask the model to return only score>=0.4 pairs to keep output small.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

from ..llm import LLM
from ..llm.prompts import RELEVANCE_SYSTEM, RELEVANCE_USER_TEMPLATE
from ..models import ResumeData, JDMatrix


class RelevancePair(BaseModel):
    bullet_id: str
    requirement_id: str
    score: float = Field(ge=0.0, le=1.0)
    relation: Literal["direct", "adjacent", "none"]


class RelevanceMatrix(BaseModel):
    pairs: list[RelevancePair] = Field(default_factory=list)


class BulletRelevance(BaseModel):
    bullet_id: str
    owner_id: str  # experience or project id
    best_score: float = 0.0
    matched_req_ids: list[str] = Field(default_factory=list)
    relations: dict[str, str] = Field(default_factory=dict)


class RelevanceMap(BaseModel):
    by_bullet: dict[str, BulletRelevance] = Field(default_factory=dict)
    experience_score: dict[str, float] = Field(default_factory=dict)
    project_score: dict[str, float] = Field(default_factory=dict)
    coverage_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict, description="req_id -> list of bullet ids covering it"
    )


def score_relevance(resume: ResumeData, jd: JDMatrix, llm: LLM) -> RelevanceMap:
    if not jd.requirements:
        return RelevanceMap()

    bullets = resume.all_bullets()
    if not bullets:
        return RelevanceMap()

    bullets_block = "\n".join(
        f"[{b.id} | owner={owner_id}] {b.text}" for owner_id, b in bullets
    )
    requirements_block = "\n".join(
        f"[{r.id} | {r.category} | {r.importance}] {r.text}" for r in jd.requirements
    )

    matrix = llm.structured(
        schema=RelevanceMatrix,
        system=RELEVANCE_SYSTEM,
        user=RELEVANCE_USER_TEMPLATE.format(
            requirements_block=requirements_block,
            bullets_block=bullets_block,
        ),
        tool_name="emit_relevance",
        tool_description="Emit relevance pairs (score >= 0.4 only).",
        heavy=False,
        max_tokens=8192,
        temperature=0.0,
    )

    # Build a quick lookup of valid IDs to filter out hallucinated ids.
    bullet_owner: dict[str, str] = {b.id: owner for owner, b in bullets}
    valid_req: set[str] = {r.id for r in jd.requirements}

    rmap = RelevanceMap()
    for pair in matrix.pairs:
        if pair.bullet_id not in bullet_owner or pair.requirement_id not in valid_req:
            continue
        owner = bullet_owner[pair.bullet_id]
        br = rmap.by_bullet.get(pair.bullet_id)
        if br is None:
            br = BulletRelevance(bullet_id=pair.bullet_id, owner_id=owner)
            rmap.by_bullet[pair.bullet_id] = br
        if pair.score > br.best_score:
            br.best_score = pair.score
        if pair.requirement_id not in br.matched_req_ids:
            br.matched_req_ids.append(pair.requirement_id)
        br.relations[pair.requirement_id] = pair.relation
        rmap.coverage_by_requirement.setdefault(pair.requirement_id, []).append(pair.bullet_id)

    # Aggregate per owner (experience / project) — average of top-3 bullets.
    by_owner: dict[str, list[float]] = {}
    for br in rmap.by_bullet.values():
        by_owner.setdefault(br.owner_id, []).append(br.best_score)
    for owner_id, scores in by_owner.items():
        scores.sort(reverse=True)
        topk = scores[:3]
        agg = sum(topk) / len(topk) if topk else 0.0
        # Distinguish experience vs project owners by prefix.
        if owner_id.startswith("exp_"):
            rmap.experience_score[owner_id] = agg
        elif owner_id.startswith("prj_"):
            rmap.project_score[owner_id] = agg

    return rmap
