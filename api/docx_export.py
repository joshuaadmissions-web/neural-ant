from __future__ import annotations

import io
import re
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


MONTHS = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
MONTH_YEAR = rf"(?:{MONTHS})\s+20\d{{2}}"
DATE_RANGE_LINE = re.compile(rf"^(?P<title>.+?)\s+(?P<start>{MONTH_YEAR})\s*[–—-]\s*(?P<end>Present|Current|{MONTH_YEAR})$", re.I)
DATE_RANGE_SEARCH = re.compile(rf"(?P<start>{MONTH_YEAR})\s*[–—-]\s*(?P<end>Present|Current|{MONTH_YEAR})", re.I)
BODY_SIZE = 9.6
CONTENT_WIDTH_IN = 7.4


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean_line(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"^[•·▪◦–—-]\s*", "", value).strip()


def _source_lines(source_text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in _text(source_text).splitlines() if line.strip()]


def _section(lines: list[str], heading: str, end_heading: str | None = None) -> list[str]:
    try:
        start = next(index for index, line in enumerate(lines) if line.casefold() == heading.casefold()) + 1
    except StopIteration:
        return []
    end = len(lines)
    if end_heading:
        for index in range(start, len(lines)):
            if lines[index].casefold() == end_heading.casefold():
                end = index
                break
    return lines[start:end]


def _split_company_location(value: str) -> tuple[str, str]:
    value = _clean_line(value)
    match = re.search(r",\s*(?P<region>[A-Z]{2}|India|Canada|United States)$", value)
    if not match:
        return value.strip(), ""
    before = value[:match.start()].strip(" ,")
    if not before or " " not in before:
        return value.strip(), ""
    city = before.rsplit(" ", 1)[-1]
    company = before[: -len(city)].strip(" ,")
    return company or value.strip(), f"{city}, {match.group('region').strip()}"


def _join_bullets(lines: list[str], marker_pattern: str = r"[-–—]") -> list[str]:
    bullets: list[str] = []
    current = ""
    for line in lines:
        value = line.strip()
        if re.match(rf"^(?:{marker_pattern})\s*", value):
            if current:
                bullets.append(current.strip())
            current = re.sub(rf"^(?:{marker_pattern})\s*", "", value).strip()
        elif current:
            current = f"{current} {value}".strip()
    if current:
        bullets.append(current.strip())
    return [re.sub(r"\s+", " ", bullet) for bullet in bullets if len(bullet) >= 12]


def _source_experience(source_text: str) -> list[dict[str, Any]]:
    lines = _section(_source_lines(source_text), "Experience", "Projects")
    date_indexes = [(index, DATE_RANGE_LINE.match(line)) for index, line in enumerate(lines)]
    date_indexes = [(index, match) for index, match in date_indexes if match]
    records: list[dict[str, Any]] = []
    for position, (date_index, match) in enumerate(date_indexes):
        next_date_index = date_indexes[position + 1][0] if position + 1 < len(date_indexes) else len(lines)
        company_line = _clean_line(lines[date_index - 1]) if date_index else ""
        company, location = _split_company_location(company_line)
        bullet_end = max(date_index + 1, next_date_index - 1)
        bullets = _join_bullets(lines[date_index + 1 : bullet_end])
        records.append({
            "company": company,
            "title": match.group("title").strip(),
            "start_date": match.group("start").strip(),
            "end_date": match.group("end").strip(),
            "location": location,
            "bullets": bullets,
        })
    return [record for record in records if record["company"] and record["title"]]


def _split_highlights(value: Any) -> list[str]:
    chunks = re.split(r"\n+|;(?=\s*[A-Z])", _text(value))
    return [re.sub(r"\s+", " ", _clean_line(chunk)) for chunk in chunks if len(_clean_line(chunk)) >= 12]


def _profile_experience(profile: dict[str, Any], draft_content: str) -> list[dict[str, Any]]:
    records = profile.get("employment_history") if isinstance(profile.get("employment_history"), list) else []
    result: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        result.append({
            "company": _text(record.get("company")),
            "title": _text(record.get("title")),
            "start_date": _text(record.get("start_date")),
            "end_date": _text(record.get("end_date")),
            "location": _text(record.get("location")),
            "bullets": _split_highlights(record.get("highlights")),
        })
    return [record for record in result if record["company"] or record["title"]]


def _source_projects(source_text: str) -> list[tuple[str, str]]:
    lines = _section(_source_lines(source_text), "Projects", "Education")
    projects: list[tuple[str, str]] = []
    for bullet in _join_bullets(lines, r"[•]"):
        name, separator, description = bullet.partition(":")
        if separator:
            projects.append((name.strip(), description.strip()))
        elif bullet:
            projects.append(("", bullet))
    return projects


def _source_skills(source_text: str, profile: dict[str, Any]) -> list[tuple[str, str]]:
    lines = _section(_source_lines(source_text), "Skills", "Experience")
    skills: list[tuple[str, str]] = []
    for line in lines:
        label, separator, values = line.partition(":")
        if separator and len(label) <= 40:
            skills.append((_clean_line(label), values.strip()))
    if skills:
        return skills
    confirmed = [_text(item) for item in profile.get("skills", []) if _text(item)]
    return [("Skills", ", ".join(confirmed))] if confirmed else []


def _source_education(source_text: str, profile: dict[str, Any]) -> list[dict[str, str]]:
    lines = _section(_source_lines(source_text), "Education")
    records: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        match = DATE_RANGE_SEARCH.search(line)
        if not match or index == 0:
            continue
        school, location = _split_company_location(lines[index - 1])
        degree = line[:match.start()].strip()
        records.append({
            "school": school,
            "location": location,
            "degree": degree,
            "start_date": match.group("start").strip(),
            "end_date": match.group("end").strip(),
        })
    if records:
        return records
    fallback = profile.get("education_history") if isinstance(profile.get("education_history"), list) else []
    result: list[dict[str, str]] = []
    for record in fallback:
        if isinstance(record, dict):
            result.append({
                "school": _text(record.get("school")),
                "location": _text(record.get("location")),
                "degree": " ".join(part for part in (_text(record.get("degree")), _text(record.get("field"))) if part),
                "start_date": _text(record.get("start_date")),
                "end_date": _text(record.get("end_date")),
            })
    return result


def _relevance_terms(profile: dict[str, Any], job: Any) -> list[str]:
    skills = [_text(item).casefold() for item in profile.get("skills", []) if _text(item)]
    title_words = re.findall(r"[a-z][a-z+#.-]{3,}", _text(getattr(job, "title", "")).casefold())
    return list(dict.fromkeys(sorted(skills + title_words, key=len, reverse=True)))


def _relevance_score(value: str, terms: list[str], job_description: str) -> int:
    lower = value.casefold()
    job_lower = job_description.casefold()
    return sum(1 for term in terms if term in job_lower and term in lower)


def _set_run_font(run, size: float = BODY_SIZE, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def _compact_paragraph(paragraph, *, before: float = 0, after: float = 0, line_spacing: float = 0.92) -> None:
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = line_spacing


def _add_bottom_border(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    borders.append(bottom)


def _section_heading(document: Document, label: str) -> None:
    paragraph = document.add_paragraph()
    _compact_paragraph(paragraph, before=4, after=1, line_spacing=0.88)
    paragraph.paragraph_format.keep_with_next = True
    _add_bottom_border(paragraph)
    _set_run_font(paragraph.add_run(label), size=13.4)


def _right_tab(paragraph) -> None:
    paragraph.paragraph_format.tab_stops.add_tab_stop(Inches(CONTENT_WIDTH_IN), WD_TAB_ALIGNMENT.RIGHT)


def _add_role(document: Document, record: dict[str, Any], terms: list[str], job_description: str) -> None:
    company = _text(record.get("company"))
    location = _text(record.get("location"))
    title = _text(record.get("title"))
    dates = " – ".join(part for part in (_text(record.get("start_date")), _text(record.get("end_date"))) if part)

    heading = document.add_paragraph()
    _compact_paragraph(heading, before=1, after=0, line_spacing=0.88)
    heading.paragraph_format.keep_with_next = True
    _right_tab(heading)
    _set_run_font(heading.add_run("• "))
    _set_run_font(heading.add_run(company), bold=True)
    if location:
        _set_run_font(heading.add_run(f"\t{location}"))

    role_line = document.add_paragraph()
    _compact_paragraph(role_line, after=0, line_spacing=0.86)
    role_line.paragraph_format.keep_with_next = True
    role_line.paragraph_format.left_indent = Inches(0.15)
    _right_tab(role_line)
    _set_run_font(role_line.add_run(title), italic=True)
    if dates:
        _set_run_font(role_line.add_run(f"\t{dates}"), italic=True)

    bullets = list(record.get("bullets") or [])
    bullets.sort(key=lambda value: _relevance_score(value, terms, job_description), reverse=True)
    for bullet in bullets:
        paragraph = document.add_paragraph()
        _compact_paragraph(paragraph, after=0, line_spacing=0.9)
        paragraph.paragraph_format.left_indent = Inches(0.34)
        paragraph.paragraph_format.first_line_indent = Inches(-0.18)
        _set_run_font(paragraph.add_run("– "))
        _set_run_font(paragraph.add_run(bullet))


def _add_project(document: Document, name: str, description: str) -> None:
    paragraph = document.add_paragraph()
    _compact_paragraph(paragraph, after=0, line_spacing=0.9)
    paragraph.paragraph_format.left_indent = Inches(0.18)
    paragraph.paragraph_format.first_line_indent = Inches(-0.18)
    _set_run_font(paragraph.add_run("• "))
    if name:
        _set_run_font(paragraph.add_run(name), bold=True)
        _set_run_font(paragraph.add_run(": "))
    _set_run_font(paragraph.add_run(description))


def _add_education(document: Document, record: dict[str, str]) -> None:
    school_line = document.add_paragraph()
    _compact_paragraph(school_line, before=1, after=0, line_spacing=0.88)
    school_line.paragraph_format.keep_with_next = True
    _right_tab(school_line)
    _set_run_font(school_line.add_run("• "))
    _set_run_font(school_line.add_run(_text(record.get("school"))), bold=True)
    if _text(record.get("location")):
        _set_run_font(school_line.add_run(f"\t{_text(record.get('location'))}"))

    degree_line = document.add_paragraph()
    _compact_paragraph(degree_line, after=0, line_spacing=0.86)
    degree_line.paragraph_format.left_indent = Inches(0.15)
    _right_tab(degree_line)
    _set_run_font(degree_line.add_run(_text(record.get("degree"))), italic=True)
    dates = " – ".join(part for part in (_text(record.get("start_date")), _text(record.get("end_date"))) if part)
    if dates:
        _set_run_font(degree_line.add_run(f"\t{dates}"), italic=True)


def build_resume_docx(profile: dict[str, Any], job: Any, draft_content: str, source_text: str = "") -> bytes:
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.38)
    section.bottom_margin = Inches(0.38)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)
    section.header_distance = Inches(0.2)
    section.footer_distance = Inches(0.2)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.font.size = Pt(BODY_SIZE)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 0.92

    name = _text(profile.get("preferred_name")) or _text(profile.get("name")) or "Candidate Resume"
    title = _text(getattr(job, "title", "Target role"))
    company = _text(getattr(job, "company_name", ""))
    document.core_properties.title = f"{title} Resume"
    document.core_properties.subject = f"Resume draft for {title} at {company}".strip()

    name_paragraph = document.add_paragraph()
    name_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _compact_paragraph(name_paragraph, after=0, line_spacing=0.82)
    _set_run_font(name_paragraph.add_run(name.upper()), size=17.5, bold=True)

    location = _text(profile.get("location"))
    phone = _text(profile.get("phone"))
    email = _text(profile.get("email"))
    links = [item for item in (_text(profile.get("linkedin_url")), _text(profile.get("github_url")), _text(profile.get("portfolio_url")), _text(profile.get("website_url"))) if item]
    contact_lines = [" | ".join(item for item in (location, phone) if item), " | ".join(item for item in (email, *links) if item)]
    for value in contact_lines:
        if not value:
            continue
        contact = document.add_paragraph()
        contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _compact_paragraph(contact, after=0, line_spacing=0.82)
        _set_run_font(contact.add_run(value), size=10.1)

    skills = _source_skills(source_text, profile)
    job_description = _text(getattr(job, "description", ""))
    terms = _relevance_terms(profile, job)
    skills = sorted(skills, key=lambda item: _relevance_score(f"{item[0]} {item[1]}", terms, job_description), reverse=True)
    if skills:
        _section_heading(document, "Skills")
        for index, (label, values) in enumerate(skills):
            paragraph = document.add_paragraph()
            _compact_paragraph(paragraph, line_spacing=0.86)
            paragraph.paragraph_format.left_indent = Inches(0.18)
            paragraph.paragraph_format.first_line_indent = Inches(-0.18) if index == 0 else Inches(0)
            if index == 0:
                _set_run_font(paragraph.add_run("• "))
            _set_run_font(paragraph.add_run(f"{label}: "), bold=True)
            _set_run_font(paragraph.add_run(values))

    _section_heading(document, "Experience")
    records = _source_experience(source_text) or _profile_experience(profile, draft_content)
    for record in records:
        _add_role(document, record, terms, job_description)

    projects = _source_projects(source_text)
    if projects:
        _section_heading(document, "Projects")
        for name_value, description in projects:
            _add_project(document, name_value, description)

    education = _source_education(source_text, profile)
    if education:
        _section_heading(document, "Education")
        for record in education:
            _add_education(document, record)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
