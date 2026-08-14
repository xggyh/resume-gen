"""Render OutputResume → HTML (and Markdown debug view)."""

from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, BaseLoader, select_autoescape

from ..models import OutputResume


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _load_template_str(name: str) -> str:
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


def render_html(resume: OutputResume, template: str = "classic") -> str:
    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html"]))
    html_template = env.from_string(_load_template_str(f"{template}.html"))
    css = _load_template_str(f"{template}.css")
    return html_template.render(resume=resume, css=css)


def render_markdown(resume: OutputResume) -> str:
    L = resume.section_labels or {}
    def label(key: str, default: str) -> str:
        return L.get(key, default)

    out: list[str] = []
    bi = resume.basic_info
    out.append(f"# {bi.name}")
    if bi.headline:
        out.append(f"_{bi.headline}_")
    contact = " · ".join(
        v for v in [bi.email, bi.phone, bi.location, bi.linkedin, bi.github, bi.website] if v
    )
    if contact:
        out.append(contact)
    out.append("")

    if resume.professional_summary_bullets:
        out.append(f"## {label('summary', 'Professional Summary')}")
        for b in resume.professional_summary_bullets:
            out.append(f"- {b}")
        out.append("")
    elif resume.professional_summary:
        out.append(f"## {label('summary', 'Professional Summary')}")
        out.append(resume.professional_summary)
        out.append("")

    if resume.experiences:
        out.append(f"## {label('experience', 'Work Experience')}")
        for exp in resume.experiences:
            dates = " – ".join(filter(None, [exp.start_date, exp.end_date])) or ""
            loc = f" · {exp.location}" if exp.location else ""
            out.append(f"### {exp.role} · {exp.company}{loc}")
            if dates:
                out.append(f"_{dates}_")
            if exp.summary_line:
                out.append(f"_{exp.summary_line}_")
            if exp.sub_sections:
                for sub in exp.sub_sections:
                    heading = f"**_{sub.title}_**"
                    if sub.date_range:
                        heading += f" — {sub.date_range}"
                    out.append(heading)
                    if sub.summary_line:
                        out.append(f"_{sub.summary_line}_")
                    for b in sub.bullets:
                        out.append(f"- {b.text}")
                    out.append("")
            else:
                for b in exp.bullets:
                    out.append(f"- {b.text}")
                out.append("")

    if resume.projects:
        out.append(f"## {label('projects', 'Selected Projects')}")
        for prj in resume.projects:
            extras = " · ".join(filter(None, [prj.role, prj.organization]))
            head = f"### {prj.name}"
            if extras:
                head += f" — {extras}"
            out.append(head)
            dates = " – ".join(filter(None, [prj.start_date, prj.end_date]))
            if dates:
                out.append(f"_{dates}_")
            if prj.tech_stack:
                out.append(f"**Tech:** {', '.join(prj.tech_stack)}")
            for b in prj.bullets:
                out.append(f"- {b.text}")
            out.append("")

    if resume.education:
        out.append(f"## {label('education', 'Education')}")
        for ed in resume.education:
            dates = " – ".join(filter(None, [ed.start_date, ed.end_date]))
            field = f", {ed.field}" if ed.field else ""
            line = f"### {ed.degree}{field} · {ed.institution}"
            out.append(line)
            metas: list[str] = []
            if dates:
                metas.append(dates)
            if ed.gpa:
                metas.append(f"GPA: {ed.gpa}")
            if metas:
                out.append(f"_{' | '.join(metas)}_")
            for h in ed.highlights:
                out.append(f"- {h}")
            out.append("")

    if resume.publications:
        out.append(f"## {label('publications', 'Publications')}")
        for p in resume.publications:
            extras = []
            if p.venue:
                extras.append(p.venue)
            if p.year:
                extras.append(p.year)
            line = f"- _{p.title}_"
            if extras:
                line += f" — {', '.join(extras)}"
            if p.authors:
                line += f". {p.authors}"
            out.append(line)
        out.append("")

    if resume.talks:
        out.append(f"## {label('talks', 'Selected Talks & Tech Sharing')}")
        for t in resume.talks:
            extras = []
            if t.venue:
                extras.append(t.venue)
            if t.audience:
                extras.append(t.audience)
            if t.year:
                extras.append(t.year)
            line = f"- **{t.title}**"
            if extras:
                line += f" — {', '.join(extras)}"
            out.append(line)
        out.append("")

    if resume.awards:
        out.append(f"## {label('awards', 'Awards & Achievements')}")
        for a in resume.awards:
            extras = []
            if a.issuer:
                extras.append(a.issuer)
            if a.year:
                extras.append(a.year)
            line = f"- {a.title}"
            if extras:
                line += f" — {', '.join(extras)}"
            out.append(line)
        out.append("")

    if resume.certifications:
        out.append(f"## {label('certifications', 'Certifications')}")
        for c in resume.certifications:
            extras = []
            if c.issuer:
                extras.append(c.issuer)
            if c.year:
                extras.append(c.year)
            line = f"- {c.name}"
            if extras:
                line += f" — {', '.join(extras)}"
            out.append(line)
        out.append("")

    if resume.skills_groups:
        out.append(f"## {label('skills', 'Skills')}")
        for group_name, group_skills in resume.skills_groups.items():
            out.append(f"**{group_name}:** {' · '.join(group_skills)}")
        out.append("")
    elif resume.core_skills:
        out.append(f"## {label('skills', 'Skills')}")
        out.append(" · ".join(resume.core_skills))
        out.append("")

    if resume.languages:
        out.append(f"## {label('languages', 'Languages')}")
        out.append(" · ".join(resume.languages))
        out.append("")

    return "\n".join(out).rstrip() + "\n"
