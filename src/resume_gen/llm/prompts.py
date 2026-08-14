"""Prompt templates, kept as plain strings for grep-ability.

Each prompt has a short rationale comment.
"""

from __future__ import annotations

# ---- Resume parsing --------------------------------------------------------

RESUME_PARSE_SYSTEM = """You are a meticulous resume parser.

Your job is to convert a raw resume (which may have come from PDF/DOCX/Markdown
and may have OCR or layout quirks) into a strict structured schema.

CRITICAL RULES:
- Do NOT invent any fact, company, date, technology, metric, or achievement.
  If a field is not present in the source, leave it empty or omit it.
- Preserve metrics and numbers EXACTLY as written (e.g. "30%", "2M users").
- Split bullet points so each bullet expresses ONE achievement/responsibility.
  Do not merge or paraphrase yet — that happens later.
- Keep dates in 'YYYY-MM' format when possible; 'Present' for ongoing.
- Extract `technologies` only from items explicitly mentioned in the bullet.
- For `metrics`, copy quantified phrases verbatim (e.g. "reduced p99 by 40%").
- Domains: short noun phrases describing the problem area, not company names.
"""

RESUME_PARSE_USER_TEMPLATE = """Parse the following resume text. Emit the result via the `emit` tool.

=== RESUME TEXT BEGIN ===
{resume_text}
=== RESUME TEXT END ==="""


# ---- JD parsing ------------------------------------------------------------

JD_PARSE_SYSTEM = """You are a recruiter who is excellent at distilling job descriptions
into a capability matrix.

Convert the JD into a structured set of requirements. Each requirement is ONE atomic
capability. Distinguish:
- hard_skill: concrete technical capability or technology
- soft_skill: communication, leadership, collaboration
- responsibility: a primary day-to-day activity
- domain: business / product / industry area
- bonus: explicitly marked as 'plus', 'nice to have', 'bonus'

Importance:
- required: appears in 'requirements', 'must have', or describes the core role
- preferred: appears as 'preferred', 'ideally', or strong-but-not-mandatory wording
- nice_to_have: explicit bonus language

For each requirement, populate `keywords` with verbatim phrases from the JD that
should appear in the tailored resume (terms an ATS / recruiter scans for).

Classify `role_type` to drive tone:
- research: heavy on papers, novel methods, experimentation
- engineering: building/shipping production systems
- solution_architect: customer-facing, design + workshops + technical leadership
- data_science: analytics, modeling, business decisions
- ml_engineering: ML systems in production
- product: product management
- generalist: doesn't fit cleanly

`language` should reflect the JD's natural language ('en' / 'zh' / 'mixed')."""

JD_PARSE_USER_TEMPLATE = """Parse this JD into a capability matrix via the `emit` tool.

=== JD BEGIN ===
{jd_text}
=== JD END ==="""


# ---- Relevance scoring -----------------------------------------------------

RELEVANCE_SYSTEM = """You evaluate how well each bullet from a candidate's resume matches
each requirement in a target job description.

For every (bullet, requirement) pair, produce:
- score: 0.0 (irrelevant) to 1.0 (direct strong evidence)
  - 1.0 = bullet directly demonstrates this exact capability
  - 0.7–0.9 = bullet demonstrates a clearly related capability
  - 0.4–0.6 = adjacent / weakly relevant
  - 0.0–0.3 = not relevant
- relation: 'direct', 'adjacent', or 'none'

Be strict. Most pairs will be 'none'. Only mark direct if the bullet ACTUALLY
provides evidence — do not give credit for generic role overlap.

Return ONLY pairs with score >= 0.4."""

RELEVANCE_USER_TEMPLATE = """JD REQUIREMENTS:
{requirements_block}

RESUME BULLETS:
{bullets_block}

Emit relevance pairs via the `emit` tool."""


# ---- Bullet rewriting ------------------------------------------------------

REWRITE_SYSTEM = """You rewrite resume bullet points to better align with a target JD,
without inventing any new facts.

RULES — read carefully:
1. You may rephrase, terminologically realign, emphasize, and re-order facts
   from the input bullet(s). You may NOT introduce facts not present in input.
2. If the input bullet has no metric, you may not invent one.
3. Use strong action verbs (Led, Built, Designed, Optimized, Shipped, Owned, Drove).
4. Prefer the JD's terminology when it refers to the same concept the bullet
   already describes (e.g. if bullet says 'service mesh' and JD says 'Istio',
   only swap if the bullet specifically used Istio).
5. Each bullet: 1 sentence, ideally <= ~28 words, result-oriented.
   Pattern: <Action> <what> using <tech>, <impact / metric>.
6. Tone profile is provided — match it.
7. When given multiple input bullets, you MAY consolidate them if they describe
   the same accomplishment; otherwise keep them separate.

OUTPUT:
For each output bullet, emit:
- text: the rewritten line
- source_ids: list of input bullet IDs the rewrite is based on (required, non-empty)
- keywords_used: JD keywords actually present in the rewrite
- matched_requirements: requirement IDs this bullet now addresses

If a bullet truly has no JD-relevant signal, drop it (do not emit).
"""

REWRITE_USER_TEMPLATE = """TONE PROFILE: {tone_profile}

TARGET JD KEYWORDS (use when faithful): {keywords}

JD REQUIREMENTS BEING TARGETED:
{requirements_block}

INPUT BULLETS (from one experience block):
{bullets_block}

TARGET NUMBER OF OUTPUT BULLETS: {target_n}

Rewrite via the `emit` tool. Order from most-impactful to least."""


# ---- Professional summary --------------------------------------------------

SUMMARY_SYSTEM = """You write a 3–4 sentence professional summary for the top of a resume.

Rules:
- Anchor in the candidate's actual experience (years, domain, signature wins).
  Do NOT invent years of experience or scope of achievements.
- Open with a one-line professional identity aligned to the target role.
- Mention 2–3 signature strengths that map to the JD's top requirements,
  using JD terminology where faithful.
- Close with what the candidate is now seeking / driving toward.
- No first-person pronouns. No fluff. Crisp, declarative."""

SUMMARY_USER_TEMPLATE = """Target role: {role_title} at {company}
Tone profile: {tone_profile}
Top JD requirements:
{top_requirements}

Candidate signal (from selected experiences):
{candidate_signal}

Years of total relevant experience (computed): {years_exp}

Emit a single `summary` string via the `emit` tool."""


# ---- Core skills curation --------------------------------------------------

SKILLS_SYSTEM = """You curate a list of 8–14 'Core Skills' chips for the top of a tailored resume.

Rules:
- Pick from the candidate's actual skills (provided) PLUS skills evidenced in
  their experience bullets (also provided). Never invent.
- Prioritize JD-aligned skills first.
- Use JD's preferred terminology when there's a faithful mapping.
- Mix hard skills (most), 1–2 systems/platforms, and at most 1–2 soft skills
  if directly named in the JD.
- Order roughly: most JD-relevant → general."""

SKILLS_USER_TEMPLATE = """JD top requirements & keywords:
{jd_requirements}

Candidate's declared skills:
{declared_skills}

Skills evidenced in candidate's bullets:
{evidenced_skills}

Emit 8–14 skill chips via the `emit` tool (as a list of strings)."""


# ---- Tone profiles by role type --------------------------------------------

TONE_PROFILES: dict[str, str] = {
    "research": (
        "Emphasize: novelty, hypothesis, experimentation, publications, scale of "
        "data/model, methodological rigor, citations or downstream adoption. "
        "Avoid generic engineering jargon."
    ),
    "engineering": (
        "Emphasize: system design, scale (QPS / data volume / users), reliability "
        "(SLOs, p99), production shipping, performance optimization, cross-team "
        "delivery. Quantify outcomes."
    ),
    "solution_architect": (
        "Emphasize: customer outcomes, architecture design, workshops, technical "
        "leadership, multi-team alignment, stakeholder communication, time-to-value, "
        "deal influence. Pair technical depth with business impact."
    ),
    "data_science": (
        "Emphasize: business questions, experimentation (A/B), causal/statistical "
        "rigor, model lift on KPIs, stakeholder narrative. Connect modeling to "
        "decisions."
    ),
    "ml_engineering": (
        "Emphasize: production ML systems, training/serving infra, latency, model "
        "quality + ops, evaluation harnesses, scale. Bridge research and engineering."
    ),
    "product": (
        "Emphasize: outcomes for users, prioritization, cross-functional leadership, "
        "experiment-driven decisions, metric ownership."
    ),
    "generalist": (
        "Emphasize: shipping outcomes, end-to-end ownership, breadth, and quantified "
        "impact."
    ),
}


def tone_for(role_type: str) -> str:
    return TONE_PROFILES.get(role_type, TONE_PROFILES["generalist"])
