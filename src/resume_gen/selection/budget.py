"""Decide which experiences/projects to include and how many bullets per block.

A typical 2-page resume has 16–22 bullets across experience + project sections.
We allocate proportional to relevance × recency, with sensible floors and caps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

from ..models import ResumeData
from ..matching.relevance import RelevanceMap


DEFAULT_TOTAL_BULLET_BUDGET = 20
MIN_BULLETS_PER_BLOCK = 2
MAX_BULLETS_PER_BLOCK = 6
MAX_EXPERIENCES = 4
MAX_PROJECTS = 3


@dataclass
class RewriteBlock:
    kind: Literal["experience", "project"]
    owner_id: str
    source_bullet_ids: list[str]  # bullets to feed the rewriter (already ranked)
    target_n: int                  # how many output bullets to produce
    relevance: float = 0.0
    recency_weight: float = 1.0


@dataclass
class RewritePlan:
    blocks: list[RewriteBlock] = field(default_factory=list)
    dropped_experience_ids: list[str] = field(default_factory=list)
    dropped_project_ids: list[str] = field(default_factory=list)


# ---- recency ---------------------------------------------------------------


def _parse_year_month(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = s.strip()
    if s.lower() == "present":
        return date.today()
    m = re.match(r"(\d{4})[-/]?(\d{1,2})?", s)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 6
    try:
        return date(year, max(1, min(12, month)), 1)
    except ValueError:
        return None


def _recency_weight(end: Optional[str]) -> float:
    """Years-ago → weight in (0.4, 1.0]."""
    d = _parse_year_month(end)
    if d is None:
        return 0.6
    years_ago = max(0.0, (date.today() - d).days / 365.25)
    # ~1.0 for current role, ~0.85 at 2y ago, ~0.6 at 6y, floored at 0.4
    return max(0.4, 1.0 - 0.07 * years_ago)


# ---- planning --------------------------------------------------------------


def build_rewrite_plan(
    resume: ResumeData,
    relevance: RelevanceMap,
    total_budget: int = DEFAULT_TOTAL_BULLET_BUDGET,
) -> RewritePlan:
    plan = RewritePlan()

    # 1. Rank experiences (relevance × recency)
    exp_scored: list[tuple[float, str, float, float]] = []  # (weight, id, relevance, recency)
    for exp in resume.experiences:
        rel = relevance.experience_score.get(exp.id, 0.0)
        rec = _recency_weight(exp.end_date)
        w = (0.15 + rel) * rec  # floor so very recent but unrelated still counts
        exp_scored.append((w, exp.id, rel, rec))
    exp_scored.sort(reverse=True)

    selected_exps = exp_scored[:MAX_EXPERIENCES]
    plan.dropped_experience_ids = [eid for _, eid, _, _ in exp_scored[MAX_EXPERIENCES:]]

    # 2. Rank projects similarly
    prj_scored: list[tuple[float, str, float, float]] = []
    for prj in resume.projects:
        rel = relevance.project_score.get(prj.id, 0.0)
        rec = _recency_weight(prj.end_date)
        w = (0.1 + rel) * rec
        prj_scored.append((w, prj.id, rel, rec))
    prj_scored.sort(reverse=True)
    # Only keep projects that are clearly relevant (>=0.4) OR fill space if few experiences
    keep_projects: list[tuple[float, str, float, float]] = []
    for tup in prj_scored:
        if tup[2] >= 0.4 or (len(selected_exps) < 2 and len(keep_projects) < MAX_PROJECTS):
            keep_projects.append(tup)
        if len(keep_projects) >= MAX_PROJECTS:
            break
    plan.dropped_project_ids = [pid for _, pid, _, _ in prj_scored if pid not in {t[1] for t in keep_projects}]

    # 3. Allocate bullet budget across selected blocks, proportional to weight
    blocks: list[tuple[str, str, float, float, float]] = []  # (kind, id, weight, relevance, recency)
    for w, eid, rel, rec in selected_exps:
        blocks.append(("experience", eid, w, rel, rec))
    for w, pid, rel, rec in keep_projects:
        blocks.append(("project", pid, w, rel, rec))

    if not blocks:
        return plan

    total_weight = sum(b[2] for b in blocks) or 1.0
    # Float allocations
    raw = [(b, max(MIN_BULLETS_PER_BLOCK, b[2] / total_weight * total_budget)) for b in blocks]
    # Floor + redistribute remainder
    allocations: dict[str, int] = {}
    remainder = total_budget
    for (b, x) in raw:
        n = max(MIN_BULLETS_PER_BLOCK, min(MAX_BULLETS_PER_BLOCK, int(round(x))))
        allocations[b[1]] = n
        remainder -= n
    # If we overshot or undershot, trim or grow proportional to weight
    if remainder != 0:
        order = sorted(blocks, key=lambda b: b[2], reverse=(remainder > 0))
        idx = 0
        guard = 0
        while remainder != 0 and guard < 200:
            kind, oid, _, _, _ = order[idx % len(order)]
            cur = allocations[oid]
            if remainder > 0 and cur < MAX_BULLETS_PER_BLOCK:
                allocations[oid] = cur + 1
                remainder -= 1
            elif remainder < 0 and cur > MIN_BULLETS_PER_BLOCK:
                allocations[oid] = cur - 1
                remainder += 1
            idx += 1
            guard += 1

    # 4. For each block, pick which source bullets to feed the rewriter
    bullets_by_owner: dict[str, list[tuple[str, float]]] = {}
    for bid, br in relevance.by_bullet.items():
        bullets_by_owner.setdefault(br.owner_id, []).append((bid, br.best_score))

    exp_by_id = {e.id: e for e in resume.experiences}
    prj_by_id = {p.id: p for p in resume.projects}

    for kind, oid, weight, rel, rec in blocks:
        target_n = allocations.get(oid, MIN_BULLETS_PER_BLOCK)
        # Source bullets: all relevant bullets first (sorted), then top remaining originals
        scored = sorted(bullets_by_owner.get(oid, []), key=lambda x: -x[1])
        chosen: list[str] = [bid for bid, _ in scored]

        all_bullet_ids: list[str]
        if kind == "experience":
            exp = exp_by_id.get(oid)
            all_bullet_ids = [b.id for b in (exp.bullets if exp else [])]
        else:
            prj = prj_by_id.get(oid)
            all_bullet_ids = [b.id for b in (prj.bullets if prj else [])]

        # Top up with original bullets if not enough relevance signal
        for bid in all_bullet_ids:
            if bid not in chosen and len(chosen) < target_n * 2:
                chosen.append(bid)

        plan.blocks.append(
            RewriteBlock(
                kind=kind,
                owner_id=oid,
                source_bullet_ids=chosen,
                target_n=target_n,
                relevance=rel,
                recency_weight=rec,
            )
        )

    # 5. Re-order blocks: experiences first (by recency desc), then projects (by relevance desc)
    plan.blocks.sort(
        key=lambda b: (
            0 if b.kind == "experience" else 1,
            -b.recency_weight if b.kind == "experience" else -b.relevance,
        )
    )
    return plan
