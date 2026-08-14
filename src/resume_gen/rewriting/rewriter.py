"""Rewrite bullets for one experience/project block to align with the JD.

Hallucination guardrail: every emitted bullet MUST list `source_ids` that
appear in the input. Any output bullet with unknown source_ids is dropped
(and recorded in the risk report by the quality stage).
"""

from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Literal

from ..llm import LLM
from ..llm.prompts import REWRITE_SYSTEM, REWRITE_USER_TEMPLATE, tone_for
from ..models import ResumeData, JDMatrix, OutputBullet
from ..matching.relevance import RelevanceMap
from ..selection.budget import RewriteBlock


class _RewriteOutItem(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)
    keywords_used: list[str] = Field(default_factory=list)
    matched_requirements: list[str] = Field(default_factory=list)


class _RewriteOut(BaseModel):
    bullets: list[_RewriteOutItem] = Field(default_factory=list)


@dataclass
class RewrittenBlock:
    block: RewriteBlock
    bullets: list[OutputBullet]
    dropped: list[str]  # output texts dropped during validation


def rewrite_block(
    block: RewriteBlock,
    resume: ResumeData,
    jd: JDMatrix,
    relevance: RelevanceMap,
    llm: LLM,
) -> RewrittenBlock:
    # Resolve bullet objects from id
    id_to_bullet = {b.id: b for _, b in resume.all_bullets()}
    source_bullets = [id_to_bullet[bid] for bid in block.source_bullet_ids if bid in id_to_bullet]
    if not source_bullets:
        return RewrittenBlock(block=block, bullets=[], dropped=[])

    # Collect requirements that any of these bullets covers (most-targeted set)
    req_ids: list[str] = []
    seen: set[str] = set()
    for bid in block.source_bullet_ids:
        br = relevance.by_bullet.get(bid)
        if not br:
            continue
        for rid in br.matched_req_ids:
            if rid not in seen:
                seen.add(rid)
                req_ids.append(rid)
    req_by_id = {r.id: r for r in jd.requirements}
    requirements_block = "\n".join(
        f"[{rid} | {req_by_id[rid].importance}] {req_by_id[rid].text}"
        for rid in req_ids
        if rid in req_by_id
    ) or "(no high-relevance requirements pre-matched; rewriter should focus on impact)"

    bullets_block = "\n".join(f"[{b.id}] {b.text}" for b in source_bullets)
    keywords_pool = jd.all_keywords()[:25]

    out = llm.structured(
        schema=_RewriteOut,
        system=REWRITE_SYSTEM,
        user=REWRITE_USER_TEMPLATE.format(
            tone_profile=tone_for(jd.role_type),
            keywords=", ".join(keywords_pool) or "(none)",
            requirements_block=requirements_block,
            bullets_block=bullets_block,
            target_n=block.target_n,
        ),
        tool_name="emit_bullets",
        tool_description="Emit rewritten bullets with source_ids.",
        heavy=True,  # quality matters most here
        max_tokens=4096,
        temperature=0.4,
    )

    valid_source_ids = {b.id for b in source_bullets}
    bullets: list[OutputBullet] = []
    dropped: list[str] = []

    for item in out.bullets[: block.target_n]:
        # Validate provenance — drop bullets whose source_ids don't resolve.
        clean_sources = [s for s in item.source_ids if s in valid_source_ids]
        if not clean_sources:
            dropped.append(item.text)
            continue
        bullets.append(
            OutputBullet(
                text=item.text.strip(),
                source_ids=clean_sources,
                matched_requirements=[r for r in item.matched_requirements if r in req_by_id],
                keywords_used=item.keywords_used,
            )
        )

    return RewrittenBlock(block=block, bullets=bullets, dropped=dropped)
