from __future__ import annotations

import io
import re
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor


MONTHS = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
DATE_RANGE = re.compile(rf"(?:{MONTHS})?\s*20\d{{2}}\s*(?:-|–|—|to)\s*(?:{MONTHS})?\s*(?:20\d{{2}}|present)", re.I)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean_bullet(value: str) -> str:
    value = re.sub(r"^\s*(?:[-*•–—]\s*)+", "", value)
    return re.sub(r"^\s*\d+[.)]\s*", "", value).strip()


def _split_highlights(value: Any) -> list[str]:
    chunks = re.split(r"\n+|;(?=\s*[A-Z])", _text(value))
    return [_clean_bullet(chunk) for chunk in chunks if len(_clean_bullet(chunk)) >= 12]


def _draft_experience_blocks(draft_content: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in _text(draft_content).splitlines():
        if raw.strip().lstrip("#").strip().lower().startswith("role details to verify"):
            break
        line = _clean_bullet(raw)
        if not line:
            continue
        if DATE_RANGE.search(line) and not line.startswith(("–", "—", "•")):
            current = {"heading": line, "bullets": []}
            blocks.append(current)
            continue
        if current and raw.lstrip().startswith(("-", "*", "•", "–", "—")):
            bullet = _clean_bullet(raw)
            if len(bullet) >= 20 and not re.match(r"^(?:Programming|AI & MLOps|Cloud & Scale|Messaging & Streaming|Process & Tools):", bullet, re.I):
                current["bullets"].append(bullet)
    return blocks


def _skills(profile: dict[str, Any], job: Any) -> tuple[list[str], list[str]]:
    confirmed = [_text(item) for item in profile.get("skills", []) if _text(item)]
    description = _text(getattr(job, "description", "job") if job is not None else "").lower()
    matched = [skill for skill in confirmed if skill.lower() in description]
    remaining = [skill for skill in confirmed if skill not in matched]
    return matched, remaining


def _set_run_font(run, size: float, bold: bool = False) -> None:
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)


def _section_heading(document: Document, label: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run(label.upper())
    _set_run_font(run, 10.5, bold=True)


def _body_paragraph(document: Document, value: str, *, bullet: bool = False) -> None:
    paragraph = document.add_paragraph(style="List Bullet" if bullet else None)
    paragraph.paragraph_format.space_after = Pt(2.5)
    paragraph.paragraph_format.line_spacing = 1.04
    run = paragraph.add_run(value)
    _set_run_font(run, 10, bold=False)


def _add_experience(document: Document, profile: dict[str, Any], draft_content: str) -> None:
    records = profile.get("employment_history") if isinstance(profile.get("employment_history"), list) else []
    fallback_blocks = _draft_experience_blocks(draft_content)
    entries: list[tuple[str, str, list[str]]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        company = _text(record.get("company"))
        title = _text(record.get("title"))
        dates = " – ".join(part for part in (_text(record.get("start_date")), _text(record.get("end_date"))) if part)
        location = _text(record.get("location"))
        heading = " | ".join(part for part in (title, company) if part)
        if dates:
            heading = f"{heading} | {dates}" if heading else dates
        if location:
            heading = f"{heading} | {location}" if heading else location
        if not heading and index < len(fallback_blocks):
            heading = _text(fallback_blocks[index].get("heading"))
        bullets = _split_highlights(record.get("highlights"))
        if not bullets and index < len(fallback_blocks):
            bullets = list(fallback_blocks[index].get("bullets", []))
        if heading:
            entries.append((heading, "", bullets))

    if not entries:
        entries = [(_text(item.get("heading")), "", list(item.get("bullets", []))) for item in fallback_blocks if _text(item.get("heading"))]

    for heading, _unused, bullets in entries:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(4)
        paragraph.paragraph_format.space_after = Pt(1)
        paragraph.paragraph_format.keep_with_next = True
        _set_run_font(paragraph.add_run(heading), 10.5, bold=True)
        for bullet in bullets[:8]:
            _body_paragraph(document, bullet, bullet=True)


def build_resume_docx(profile: dict[str, Any], job: Any, draft_content: str, source_text: str = "") -> bytes:
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.68)
    section.right_margin = Inches(0.68)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)

    name = _text(profile.get("preferred_name")) or _text(profile.get("name")) or "Candidate Resume"
    title = _text(getattr(job, "title", "Target role"))
    company = _text(getattr(job, "company_name", ""))
    document.core_properties.title = f"{title} Resume"
    document.core_properties.subject = f"Resume draft for {title} at {company}".strip()

    name_paragraph = document.add_paragraph(style="Title")
    name_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_paragraph.paragraph_format.space_after = Pt(1)
    _set_run_font(name_paragraph.add_run(name), 18, bold=True)

    contact = [
        _text(profile.get("location")),
        _text(profile.get("email")),
        _text(profile.get("phone")),
        _text(profile.get("linkedin_url")),
        _text(profile.get("github_url")) or _text(profile.get("portfolio_url")) or _text(profile.get("website_url")),
    ]
    contact_paragraph = document.add_paragraph()
    contact_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_paragraph.paragraph_format.space_after = Pt(7)
    _set_run_font(contact_paragraph.add_run(" | ".join(item for item in contact if item)), 9.5)

    target_paragraph = document.add_paragraph()
    target_paragraph.paragraph_format.space_after = Pt(5)
    target_paragraph.paragraph_format.keep_with_next = True
    _set_run_font(target_paragraph.add_run(f"Target role: {title}"), 10.5, bold=True)

    _section_heading(document, "Professional summary")
    summary = _text(profile.get("summary"))
    matched, remaining = _skills(profile, job)
    all_skills = matched + remaining
    if not summary and all_skills:
        role = _text(profile.get("role")) or title
        summary = f"{role} with experience in {', '.join(all_skills[:6])}. Applying these skills to {title} work focused on clear, reliable software and AI systems."
    if summary:
        _body_paragraph(document, summary)

    if all_skills:
        _section_heading(document, "Core skills")
        _body_paragraph(document, ", ".join(all_skills))

    _section_heading(document, "Professional experience")
    _add_experience(document, profile, draft_content or source_text)

    education = profile.get("education_history") if isinstance(profile.get("education_history"), list) else []
    if education:
        _section_heading(document, "Education")
        for record in education:
            if not isinstance(record, dict):
                continue
            school = _text(record.get("school"))
            degree = _text(record.get("degree"))
            field = _text(record.get("field"))
            dates = " – ".join(part for part in (_text(record.get("start_date")), _text(record.get("end_date"))) if part)
            line = " | ".join(part for part in (degree, field, school, dates) if part)
            if line:
                _body_paragraph(document, line)

    certifications = profile.get("certifications") if isinstance(profile.get("certifications"), list) else []
    certification_lines = []
    for record in certifications:
        if isinstance(record, dict):
            line = " | ".join(part for part in (_text(record.get("name")), _text(record.get("issuer")), _text(record.get("expiry"))) if part)
            if line:
                certification_lines.append(line)
    if certification_lines:
        _section_heading(document, "Certifications")
        for line in certification_lines:
            _body_paragraph(document, line, bullet=True)

    languages = profile.get("languages") if isinstance(profile.get("languages"), list) else []
    language_lines = []
    for record in languages:
        if isinstance(record, dict):
            line = " — ".join(part for part in (_text(record.get("language")), _text(record.get("proficiency"))) if part)
            if line:
                language_lines.append(line)
    if language_lines:
        _section_heading(document, "Languages")
        _body_paragraph(document, ", ".join(language_lines))

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
