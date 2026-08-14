# resume-gen

JD-tailored resume generator. Takes your original resume + a target job
description, returns a 2-page tailored resume (PDF + DOCX + HTML + Markdown)
plus a match report and a risk/provenance report.

## What it does

```
resume (PDF/DOCX/MD/TXT/JSON)         JD (MD/TXT)
              │                            │
              ▼                            ▼
       parse → ResumeData         parse → JDMatrix
              │                            │
              └────────────┬───────────────┘
                           ▼
              score relevance (bullet × requirement)
                           ▼
        plan: pick top experiences, allocate bullet budget
                           ▼
            rewrite blocks (Opus) + summary + skills
                           ▼
        render HTML/PDF (Playwright) + DOCX (python-docx)
                           ▼
     iterate: if PDF > 2 pages, drop lowest-value bullet and re-render
                           ▼
              quality checks → match + risk reports
```

Design principles:

- **No hallucination.** Every output bullet carries `source_ids` back to the
  original resume. Bullets without traceable provenance are dropped.
- **Two-page guarantee.** PDF is rendered, page count measured, lowest-value
  bullets trimmed iteratively until ≤ 2 pages.
- **ATS-friendly.** Single-column semantic HTML; DOCX generated separately
  with native heading/bullet styles (best parsing across major ATS systems).
- **JD-aware tone.** JD is classified into role-type (research / engineering /
  solution architect / data science / ML engineering / product); rewriter
  prompt uses the matching tone profile.
- **Auditability.** Every run dumps an `artifacts.json` with all intermediate
  state for inspection or replay.

## Setup

```bash
# Python 3.10+
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m playwright install chromium

# API key
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

## Usage

```bash
resume-gen run \
    --resume examples/example_resume.md \
    --jd examples/example_jd.md \
    --out ./output \
    --verbose
```

Outputs (in `./output`):

| File | Purpose |
|------|---------|
| `resume.pdf` | final 2-page tailored resume |
| `resume.docx` | ATS-friendly Word version |
| `resume.html` | preview / debug |
| `resume.md` | editable Markdown copy |
| `match_report.json` | per-requirement coverage matrix |
| `risk_report.json` | provenance trace + uncovered JD items |
| `artifacts.json` | all intermediate state (parsed resume, JD matrix, relevance scores, …) |

### Dry-run helpers

```bash
resume-gen parse-jd      examples/example_jd.md
resume-gen parse-resume  examples/example_resume.md
```

## Input formats

- **PDF** (`pdfplumber`, falls back to `pypdf`)
- **DOCX** (`python-docx`)
- **Markdown / TXT** (read as-is)
- **JSON** — if structured as `ResumeData` or `JDMatrix`, used directly (skips
  LLM parsing; highest quality)

## Architecture

```
src/resume_gen/
├── models/           # ResumeData / JDMatrix / OutputResume / Reports (Pydantic)
├── llm/              # Anthropic client wrapper + prompt library
├── ingestion/        # File → raw text
├── extraction/       # Raw text → ResumeData / JDMatrix
├── matching/         # Relevance scoring (bullet × requirement)
├── selection/        # Two-page budget allocation
├── rewriting/        # bullet rewriter, summary, skills curator
├── quality/          # Provenance, keyword coverage, ATS heuristics
├── rendering/        # HTML, PDF (Playwright), DOCX, Markdown
├── reports/          # Match + risk reports
├── pipeline.py       # End-to-end orchestrator
└── cli.py            # `resume-gen` entry point
```

## Customizing

- **Template**: drop a new `<name>.html` + `<name>.css` into
  `src/resume_gen/rendering/templates/`, then pass `--template <name>`.
- **Tone profiles**: edit `TONE_PROFILES` in `src/resume_gen/llm/prompts.py`.
- **Bullet budget / per-block caps**: see constants at top of
  `src/resume_gen/selection/budget.py`.
- **Models**: override via env vars `RESUME_GEN_MODEL_HEAVY` /
  `RESUME_GEN_MODEL_LIGHT`.

## Cost / latency

A single run on a normal-sized resume + JD makes roughly:

- 1 light call (resume parse)
- 1 light call (JD parse)
- 1 light call (relevance scoring)
- N heavy calls (one per kept experience/project, typically 4–6)
- 1 heavy call (summary)
- 1 light call (skills curation)

System prompts are cache-controlled, so repeat runs against the same JD or
same resume are cheaper than the first run.
