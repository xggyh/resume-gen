"""OutputResume → .docx via python-docx.

Built deliberately simple and ATS-friendly: single column, native paragraphs and
bullet lists, no text boxes / columns / images. Headings use Word's built-in
heading styles so ATS parsers recognize section structure.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

from ..models import OutputResume


def render_docx(resume: OutputResume, out_path: str | Path) -> Path:
    out = Path(out_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    L = resume.section_labels or {}
    def label(key: str, default: str) -> str:
        return L.get(key, default)

    doc = Document()
    _apply_global_style(doc, resume)
    _apply_margins(doc)

    # ----- Header -----
    bi = resume.basic_info
    name_p = doc.add_paragraph()
    name_p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
    name_run = name_p.add_run(bi.name)
    name_run.bold = True
    name_run.font.size = Pt(21)

    if bi.headline:
        hp = doc.add_paragraph()
        r = hp.add_run(bi.headline)
        r.italic = True
        r.font.size = Pt(10.5)

    contact_bits = [v for v in [bi.email, bi.phone, bi.location, bi.linkedin, bi.github, bi.website] if v]
    if contact_bits:
        cp = doc.add_paragraph(" · ".join(contact_bits))
        cp.runs[0].font.size = Pt(9.25)
        cp.runs[0].font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    _hrule(doc)

    # ----- Professional Summary -----
    if resume.professional_summary_bullets:
        _h2(doc, label("summary", "Professional Summary"))
        for b in resume.professional_summary_bullets:
            doc.add_paragraph(b, style="List Bullet")
    elif resume.professional_summary:
        _h2(doc, label("summary", "Professional Summary"))
        doc.add_paragraph(resume.professional_summary)

    # ----- Work Experience -----
    if resume.experiences:
        _h2(doc, label("experience", "Work Experience"))
        for exp in resume.experiences:
            head = doc.add_paragraph()
            r1 = head.add_run(f"{exp.company}")
            r1.bold = True
            head.add_run(f" · {exp.role}")
            meta_bits = []
            if exp.location:
                meta_bits.append(exp.location)
            dates = " – ".join(filter(None, [exp.start_date, exp.end_date]))
            if dates:
                meta_bits.append(dates)
            if meta_bits:
                mp = doc.add_paragraph(" | ".join(meta_bits))
                mp.runs[0].italic = True
                mp.runs[0].font.size = Pt(9.25)
                mp.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            if exp.summary_line:
                sp = doc.add_paragraph(exp.summary_line)
                sp.runs[0].italic = True
                sp.runs[0].font.size = Pt(9.5)
                sp.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            if exp.sub_sections:
                from docx.enum.text import WD_TAB_ALIGNMENT
                for sub in exp.sub_sections:
                    sp = doc.add_paragraph()
                    sp.paragraph_format.space_before = Pt(3)
                    sp.paragraph_format.space_after = Pt(0)
                    if sub.date_range:
                        sp.paragraph_format.tab_stops.add_tab_stop(
                            Inches(7.1), WD_TAB_ALIGNMENT.RIGHT,
                        )
                    sr = sp.add_run(sub.title)
                    sr.bold = True
                    sr.italic = True
                    sr.font.size = Pt(9.75)
                    if sub.date_range:
                        sp.add_run("\t")
                        dr = sp.add_run(sub.date_range)
                        dr.font.size = Pt(9.25)
                        dr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
                    if sub.summary_line:
                        ss = doc.add_paragraph()
                        ss.paragraph_format.space_before = Pt(1)
                        ss.paragraph_format.space_after = Pt(0)
                        ssr = ss.add_run(sub.summary_line)
                        ssr.italic = True
                        ssr.font.size = Pt(9.5)
                        ssr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
                    for b in sub.bullets:
                        doc.add_paragraph(b.text, style="List Bullet")
            else:
                for b in exp.bullets:
                    doc.add_paragraph(b.text, style="List Bullet")

    # ----- Selected Projects -----
    if resume.projects:
        _h2(doc, label("projects", "Selected Projects"))
        for prj in resume.projects:
            head = doc.add_paragraph()
            r = head.add_run(prj.name)
            r.bold = True
            extras = " · ".join(filter(None, [prj.role, prj.organization]))
            if extras:
                head.add_run(f" — {extras}")
            dates = " – ".join(filter(None, [prj.start_date, prj.end_date]))
            if dates:
                mp = doc.add_paragraph(dates)
                mp.runs[0].italic = True
                mp.runs[0].font.size = Pt(9.25)
            if prj.tech_stack:
                tp = doc.add_paragraph(f"Tech: {', '.join(prj.tech_stack)}")
                tp.runs[0].font.size = Pt(9.25)
                tp.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            for b in prj.bullets:
                doc.add_paragraph(b.text, style="List Bullet")

    # ----- Education -----
    if resume.education:
        _h2(doc, label("education", "Education"))
        for ed in resume.education:
            head = doc.add_paragraph()
            field = f", {ed.field}" if ed.field else ""
            r = head.add_run(f"{ed.degree}{field}")
            r.bold = True
            head.add_run(f" — {ed.institution}")
            metas = []
            dates = " – ".join(filter(None, [ed.start_date, ed.end_date]))
            if dates:
                metas.append(dates)
            if ed.gpa:
                metas.append(f"GPA: {ed.gpa}")
            if metas:
                mp = doc.add_paragraph(" | ".join(metas))
                mp.runs[0].italic = True
                mp.runs[0].font.size = Pt(9.25)
            for h in ed.highlights:
                doc.add_paragraph(h, style="List Bullet")

    # ----- Optional sections -----
    if resume.publications:
        _h2(doc, label("publications", "Publications"))
        for p in resume.publications:
            extras = ", ".join(filter(None, [p.venue, p.year]))
            line = p.title + (f" — {extras}" if extras else "")
            if p.authors:
                line += f". {p.authors}"
            doc.add_paragraph(line, style="List Bullet")

    if resume.talks:
        _h2(doc, label("talks", "Selected Talks & Tech Sharing"))
        for t in resume.talks:
            extras = []
            if t.venue:
                extras.append(t.venue)
            if t.audience:
                extras.append(t.audience)
            if t.year:
                extras.append(t.year)
            line = t.title + (f" — {', '.join(extras)}" if extras else "")
            doc.add_paragraph(line, style="List Bullet")

    if resume.awards:
        _h2(doc, label("awards", "Awards & Achievements"))
        for a in resume.awards:
            extras = ", ".join(filter(None, [a.issuer, a.year]))
            line = a.title + (f" — {extras}" if extras else "")
            doc.add_paragraph(line, style="List Bullet")

    if resume.certifications:
        _h2(doc, label("certifications", "Certifications"))
        for c in resume.certifications:
            extras = ", ".join(filter(None, [c.issuer, c.year]))
            line = c.name + (f" — {extras}" if extras else "")
            doc.add_paragraph(line, style="List Bullet")

    if resume.skills_groups:
        _h2(doc, label("skills", "Skills"))
        for group_name, group_skills in resume.skills_groups.items():
            p = doc.add_paragraph()
            r = p.add_run(f"{group_name}: ")
            r.bold = True
            r.font.size = Pt(9.75)
            tail = p.add_run(" · ".join(group_skills))
            tail.font.size = Pt(9.75)
    elif resume.core_skills:
        _h2(doc, label("skills", "Skills"))
        sp = doc.add_paragraph(" · ".join(resume.core_skills))
        sp.runs[0].font.size = Pt(9.75)

    if resume.languages:
        _h2(doc, label("languages", "Languages"))
        sp = doc.add_paragraph(" · ".join(resume.languages))
        sp.runs[0].font.size = Pt(9.75)

    doc.save(str(out))
    return out


def _apply_global_style(doc: Document, resume: OutputResume | None = None) -> None:
    """Apply font + size to the Normal style. When CJK text is detected, also set
    Word's East Asian font hint so the .docx renders Chinese cleanly in Office."""
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.25)

    if resume and _has_cjk(resume):
        from docx.oxml.ns import qn
        rpr = style.element.get_or_add_rPr()
        rFonts = rpr.find(qn("w:rFonts"))
        if rFonts is None:
            from docx.oxml import OxmlElement
            rFonts = OxmlElement("w:rFonts")
            rpr.append(rFonts)
        rFonts.set(qn("w:eastAsia"), "PingFang SC")
        rFonts.set(qn("w:eastAsiaTheme"), "minorEastAsia")


def _has_cjk(resume: OutputResume) -> bool:
    blob_parts = [resume.professional_summary or "", resume.basic_info.name or ""]
    for s in resume.core_skills:
        blob_parts.append(s)
    for exp in resume.experiences:
        blob_parts.append(exp.role)
        for b in exp.bullets:
            blob_parts.append(b.text)
        for sub in exp.sub_sections:
            blob_parts.append(sub.title)
            for b in sub.bullets:
                blob_parts.append(b.text)
    blob = " ".join(blob_parts)
    return any("一" <= ch <= "鿿" for ch in blob)


def _apply_margins(doc: Document) -> None:
    for section in doc.sections:
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)


def _h2(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(text.upper())
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x11, 0x11, 0x11)


def _hrule(doc: Document) -> None:
    """Lightweight horizontal rule via paragraph border."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "888888")
    pBdr.append(bottom)
    pPr.append(pBdr)
