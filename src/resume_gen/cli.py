"""CLI entry point.

Usage:
    resume-gen run --resume my_resume.pdf --jd jd.txt --out ./output
    resume-gen run --resume my_resume.json --jd jd.md --out ./output --template classic
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .pipeline import run_pipeline
from .llm import get_llm


app = typer.Typer(add_completion=False, help="JD-tailored resume generator.")
console = Console()


@app.command()
def run(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to original resume (.pdf/.docx/.md/.txt/.json)"),
    jd: Path = typer.Option(..., "--jd", "-j", help="Path to target JD"),
    out: Path = typer.Option(Path("./output"), "--out", "-o", help="Output directory"),
    template: str = typer.Option("classic", "--template", "-t", help="Resume template name"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run the full pipeline end-to-end."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
    )

    if not resume.exists():
        console.print(f"[red]Resume file not found: {resume}[/red]")
        raise typer.Exit(1)
    if not jd.exists():
        console.print(f"[red]JD file not found: {jd}[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit("[bold]Resume-Gen[/bold] — JD-tailored resume pipeline", border_style="cyan"))

    try:
        llm = get_llm()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2)

    with console.status("[cyan]Running pipeline...[/cyan]", spinner="dots"):
        result = run_pipeline(resume_path=resume, jd_path=jd, output_dir=out, llm=llm, template=template)

    _print_summary(result)


def _print_summary(result) -> None:
    table = Table(title="Outputs", show_header=True, header_style="bold cyan")
    table.add_column("Artifact")
    table.add_column("Path")
    table.add_row("PDF (final)", str(result.pdf_path))
    table.add_row("DOCX", str(result.docx_path))
    table.add_row("HTML", str(result.html_path))
    table.add_row("Markdown", str(result.markdown_path))
    table.add_row("Match report", str(result.match_report_path))
    table.add_row("Risk report", str(result.risk_report_path))
    table.add_row("Artifacts bundle", str(result.artifacts_path))
    console.print(table)
    color = "green" if result.page_count <= 2 else "yellow"
    console.print(f"[{color}]PDF page count: {result.page_count}[/{color}]")


@app.command(name="parse-jd")
def parse_jd_cmd(jd: Path = typer.Argument(..., help="Path to JD file")):
    """Dry-run: parse JD and print the capability matrix."""
    from .ingestion.loader import load_text
    from .extraction import parse_jd
    llm = get_llm()
    matrix = parse_jd(load_text(jd), llm)
    console.print_json(matrix.model_dump_json(indent=2))


@app.command(name="parse-resume")
def parse_resume_cmd(resume: Path = typer.Argument(..., help="Path to resume file")):
    """Dry-run: parse a resume and print the structured ResumeData."""
    from .ingestion.loader import load_text
    from .extraction import parse_resume
    llm = get_llm()
    data = parse_resume(load_text(resume), llm)
    console.print_json(data.model_dump_json(indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(main() or 0)
