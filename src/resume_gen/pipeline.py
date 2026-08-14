"""End-to-end pipeline: inputs → tailored resume + reports.

Stages:
    0. Load files (PDF/DOCX/MD/TXT/JSON)
    1. Parse resume → ResumeData
    2. Parse JD     → JDMatrix
    3. Score relevance (bullet × requirement)
    4. Plan: pick experiences/projects, allocate bullet budget
    5. Rewrite bullets per block + generate summary + curate skills
    6. Assemble OutputResume
    7. Render Markdown / HTML / PDF
    8. Enforce 2-page constraint (trim lowest-value bullets, re-render)
    9. Render DOCX
   10. Quality checks + reports
   11. Save all artifacts to output dir
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ingestion.loader import load_text
from .extraction import parse_resume, parse_jd
from .matching.relevance import score_relevance, RelevanceMap
from .selection.budget import build_rewrite_plan, RewritePlan
from .rewriting.rewriter import rewrite_block
from .rewriting.summary import generate_summary
from .rewriting.skills import curate_core_skills
from .rendering import render_html, render_markdown, render_pdf, count_pdf_pages, render_docx
from .quality.checks import run_quality_checks
from .reports.reports import build_match_report, build_risk_report
from .llm import LLM, get_llm
from .models import (
    ResumeData, JDMatrix, OutputResume, OutputExperience, OutputProject, OutputBullet,
    PipelineArtifacts,
)


log = logging.getLogger("resume_gen")


MAX_PAGES = 2
MAX_TRIM_ITERATIONS = 6
MIN_BULLETS_PER_BLOCK_AFTER_TRIM = 2


@dataclass
class PipelineResult:
    output_resume: OutputResume
    pdf_path: Path
    docx_path: Path
    html_path: Path
    markdown_path: Path
    match_report_path: Path
    risk_report_path: Path
    artifacts_path: Path
    page_count: int


def run_pipeline(
    resume_path: str | Path,
    jd_path: str | Path,
    output_dir: str | Path,
    llm: Optional[LLM] = None,
    template: str = "classic",
) -> PipelineResult:
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = llm or get_llm()

    # 0. Load
    log.info("Loading inputs…")
    resume_doc = load_text(resume_path)
    jd_doc = load_text(jd_path)

    # 1+2. Parse in sequence (no race; cheap calls)
    log.info("Parsing resume…")
    resume = parse_resume(resume_doc, llm)
    log.info("Parsing JD…")
    jd = parse_jd(jd_doc, llm)

    # 3. Relevance
    log.info("Scoring relevance…")
    relevance = score_relevance(resume, jd, llm)

    # 4. Plan
    log.info("Building rewrite plan…")
    plan = build_rewrite_plan(resume, relevance)

    # 5. Rewrite all blocks
    log.info(f"Rewriting {len(plan.blocks)} blocks…")
    output_exps: list[OutputExperience] = []
    output_prjs: list[OutputProject] = []
    exp_by_id = {e.id: e for e in resume.experiences}
    prj_by_id = {p.id: p for p in resume.projects}

    for block in plan.blocks:
        rewritten = rewrite_block(block, resume, jd, relevance, llm)
        if block.kind == "experience":
            exp = exp_by_id.get(block.owner_id)
            if exp is None:
                continue
            output_exps.append(OutputExperience(
                source_id=exp.id,
                company=exp.company,
                role=exp.role,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                bullets=rewritten.bullets,
            ))
        else:
            prj = prj_by_id.get(block.owner_id)
            if prj is None:
                continue
            output_prjs.append(OutputProject(
                source_id=prj.id,
                name=prj.name,
                role=prj.role,
                organization=prj.organization,
                start_date=prj.start_date,
                end_date=prj.end_date,
                tech_stack=prj.tech_stack,
                bullets=rewritten.bullets,
                link=prj.link,
            ))

    # 6. Summary + skills
    all_selected_bullets = [b for e in output_exps for b in e.bullets] + \
                           [b for p in output_prjs for b in p.bullets]
    log.info("Generating professional summary…")
    summary = generate_summary(resume, jd, all_selected_bullets, llm)
    log.info("Curating core skills…")
    core_skills = curate_core_skills(resume, jd, llm)

    # 7. Assemble
    output_resume = OutputResume(
        basic_info=resume.basic_info,
        professional_summary=summary,
        core_skills=core_skills,
        experiences=output_exps,
        projects=output_prjs,
        education=resume.education,
        publications=resume.publications,
        awards=resume.awards,
        certifications=resume.certifications,
        target_role_title=jd.role_title,
        target_company=jd.company,
    )

    # 8. Render + enforce 2-page constraint
    log.info("Rendering & enforcing 2-page constraint…")
    pdf_path, page_count = _render_with_page_cap(output_resume, out_dir, template, jd)

    # write the (possibly trimmed) markdown + html corresponding to final output
    html_path = out_dir / "resume.html"
    md_path = out_dir / "resume.md"
    html_path.write_text(render_html(output_resume, template=template), encoding="utf-8")
    md_path.write_text(render_markdown(output_resume), encoding="utf-8")

    # 9. DOCX
    log.info("Rendering DOCX…")
    docx_path = render_docx(output_resume, out_dir / "resume.docx")

    # 10. Quality + reports
    log.info("Running quality checks…")
    q = run_quality_checks(output_resume, jd, resume)
    match_report = build_match_report(jd, output_resume, q)
    risk_report = build_risk_report(jd, resume, output_resume, q)

    match_path = out_dir / "match_report.json"
    risk_path = out_dir / "risk_report.json"
    match_path.write_text(match_report.model_dump_json(indent=2), encoding="utf-8")
    risk_path.write_text(risk_report.model_dump_json(indent=2), encoding="utf-8")

    # 11. Save artifacts bundle for replay/debugging
    artifacts = PipelineArtifacts(
        resume_raw_text=resume_doc.raw_text,
        jd_raw_text=jd_doc.raw_text,
        resume_data=resume.model_dump(),
        jd_matrix=jd.model_dump(),
        relevance=relevance.model_dump(),
        output_resume=output_resume.model_dump(),
        match_report=match_report.model_dump(),
        risk_report=risk_report.model_dump(),
    )
    artifacts_path = out_dir / "artifacts.json"
    artifacts_path.write_text(artifacts.model_dump_json(indent=2), encoding="utf-8")

    return PipelineResult(
        output_resume=output_resume,
        pdf_path=pdf_path,
        docx_path=docx_path,
        html_path=html_path,
        markdown_path=md_path,
        match_report_path=match_path,
        risk_report_path=risk_path,
        artifacts_path=artifacts_path,
        page_count=page_count,
    )


# ---- 2-page enforcement ----------------------------------------------------


def _render_with_page_cap(
    output: OutputResume,
    out_dir: Path,
    template: str,
    jd: JDMatrix,
) -> tuple[Path, int]:
    """Render PDF; if > 2 pages, drop lowest-value bullets and re-render."""
    pdf_path = out_dir / "resume.pdf"

    importance_weight = {"required": 3.0, "preferred": 2.0, "nice_to_have": 1.0}
    req_importance = {r.id: importance_weight[r.importance] for r in jd.requirements}

    for attempt in range(MAX_TRIM_ITERATIONS + 1):
        html = render_html(output, template=template)
        render_pdf(html, pdf_path)
        pages = count_pdf_pages(pdf_path)
        log.info(f"  attempt {attempt}: {pages} page(s)")
        if pages <= MAX_PAGES:
            return pdf_path, pages
        if attempt == MAX_TRIM_ITERATIONS:
            log.warning(f"Could not get under {MAX_PAGES} pages after {MAX_TRIM_ITERATIONS} trims; accepting {pages}.")
            return pdf_path, pages

        # Pick the lowest-value bullet from the largest, lowest-priority block.
        candidates: list[tuple[float, str, int]] = []  # (value, container_kind, index_in_container_bullets)

        def _value(b: OutputBullet) -> float:
            v = sum(req_importance.get(rid, 0.0) for rid in b.matched_requirements)
            v += 0.2 * len(b.keywords_used)
            v += 0.05 * len(b.text.split())  # mild penalty against long bullets being removed easily
            return v

        # iterate blocks in REVERSE priority (last block has lowest priority)
        for ei, exp in enumerate(output.experiences):
            if len(exp.bullets) <= MIN_BULLETS_PER_BLOCK_AFTER_TRIM:
                continue
            for bi, b in enumerate(exp.bullets):
                candidates.append((_value(b), f"e{ei}", bi))
        for pi, prj in enumerate(output.projects):
            if len(prj.bullets) <= MIN_BULLETS_PER_BLOCK_AFTER_TRIM:
                continue
            for bi, b in enumerate(prj.bullets):
                # projects slightly more droppable than experiences
                candidates.append((_value(b) - 0.5, f"p{pi}", bi))

        if not candidates:
            log.warning("No bullets eligible to drop; stopping trim loop.")
            return pdf_path, pages

        candidates.sort(key=lambda x: x[0])
        _, target, idx = candidates[0]
        if target.startswith("e"):
            exp_idx = int(target[1:])
            dropped = output.experiences[exp_idx].bullets.pop(idx)
        else:
            prj_idx = int(target[1:])
            dropped = output.projects[prj_idx].bullets.pop(idx)
        log.info(f"  trim: dropped bullet → '{dropped.text[:60]}...'")

    return pdf_path, count_pdf_pages(pdf_path)
