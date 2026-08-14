"""HTML → PDF via Playwright (headless Chromium).

We use Chromium because:
- It renders modern CSS reliably (the only realistic option for layout fidelity).
- print_to_pdf returns a real PDF (not an image).
- Page count is read with pypdf afterwards for the 2-page guarantee.

Caveat: Chromium's PDF text layer for CJK characters on macOS uses Kangxi
Radical lookalike codepoints (visual is fine, but copy-paste/search/ATS get
garbage). For Chinese/Japanese/Korean resumes, render via DOCX→PDF using
LibreOffice instead — see `render_pdf_from_docx()` below.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render_pdf(html: str, out_path: str | Path) -> Path:
    """Write `html` to `out_path` as PDF. Returns the path."""
    from playwright.sync_api import sync_playwright

    out = Path(out_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(out),
                format="Letter",
                margin={"top": "0.6in", "bottom": "0.6in", "left": "0.7in", "right": "0.7in"},
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            browser.close()
    return out


def count_pdf_pages(pdf_path: str | Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(pdf_path)).pages)


_LIBREOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def _find_soffice() -> str | None:
    for cand in _LIBREOFFICE_CANDIDATES:
        if "/" in cand:
            if Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def render_pdf_from_docx(docx_path: str | Path, pdf_path: str | Path) -> Path:
    """Convert .docx to .pdf via LibreOffice headless.

    Why: Chromium's PDF text layer mangles CJK characters into Kangxi Radical
    lookalikes. LibreOffice's PDF export uses the proper Unicode codepoints,
    so the resulting PDF is searchable, copy-pasteable, and ATS-friendly.

    Layout fidelity is "DOCX-as-rendered-by-Word/LibreOffice", which differs
    from the HTML/CSS template — but for CJK resumes this is the right tradeoff.
    """
    docx = Path(docx_path).expanduser().resolve()
    target = Path(pdf_path).expanduser().resolve()
    if not docx.exists():
        raise FileNotFoundError(f"DOCX not found: {docx}")

    soffice = _find_soffice()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice (soffice) not found. Install with `brew install --cask libreoffice` "
            "or add the binary to PATH. The DOCX→PDF path is needed for clean CJK text layers."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    # soffice outputs <docx_stem>.pdf into --outdir; we move it if needed.
    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(target.parent),
            str(docx),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"soffice failed: {result.stderr}\n{result.stdout}")

    produced = target.parent / f"{docx.stem}.pdf"
    if produced != target:
        produced.replace(target)
    return target
