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


def _normalise_spacing(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    # Text extracted from PDFs often separates a hyphenated word at the line
    # boundary (for example ``sub -second`` or ``third- party``). Repair only
    # hyphens whose following word starts lowercase so company names and date
    # ranges such as ``Cognizant - Trizetto`` and ``2026 – Present`` stay intact.
    value = re.sub(r"(?<=\w)\s*-\s*(?=[a-z])", "-", value)
    value = re.sub(r"(?<=[A-Za-z0-9)])\s+([,;:%)])", r"\1", value)
    return value


def _clean_line(value: str) -> str:
    value = _normalise_spacing(value)
    return re.sub(r"^[•·▪◦–—-]\s*", "", value).strip()


def _source_lines(source_text: str) -> list[str]:
    return [_normalise_spacing(line) for line in _text(source_text).splitlines() if line.strip()]


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


def _draft_summary(draft_content: str) -> str:
    lines = [re.sub(r"^\s*#+\s*", "", line).strip() for line in _text(draft_content).splitlines()]
    start = None
    for index, line in enumerate(lines):
        if line.casefold().rstrip(":") in {"professional summary", "summary", "profile"}:
            start = index + 1
            break
    if start is None:
        return ""
    values: list[str] = []
    for line in lines[start:]:
        if not line:
            if values:
                break
            continue
        if line.casefold().rstrip(":") in {"core skills", "skills", "professional experience", "experience", "projects", "education", "facts to verify"}:
            break
        cleaned = _clean_line(line)
        if cleaned:
            values.append(cleaned)
    return " ".join(values)[:700]


def _draft_sections(draft_content: str) -> dict[str, list[str]]:
    aliases = {
        "professional summary": "Professional Summary",
        "summary": "Professional Summary",
        "profile": "Professional Summary",
        "core skills": "Core Skills",
        "skills": "Core Skills",
        "technical skills": "Core Skills",
        "professional experience": "Professional Experience",
        "work experience": "Professional Experience",
        "experience": "Professional Experience",
        "projects": "Projects",
        "selected projects": "Projects",
        "education": "Education",
        "certifications": "Certifications",
    }
    sections: dict[str, list[str]] = {}
    current: str | None = None
    skipping = False
    for raw in _text(draft_content).splitlines():
        line = re.sub(r"^\s*#+\s*", "", raw).strip()
        line = line.strip("*_` ").rstrip(":").strip()
        if not line or line.startswith("```"):
            continue
        normalized = re.sub(r"\s+", " ", line).casefold()
        if normalized in aliases:
            current = aliases[normalized]
            sections.setdefault(current, [])
            skipping = False
            continue
        if normalized in {"facts to verify", "review notes", "manual checks", "notes to candidate", "cover letter"}:
            current = None
            skipping = True
            continue
        if skipping or current is None or normalized in {"resume", "tailored resume"}:
            continue
        bullet = re.match(r"^(?:[-*•▪◦])\s+(.+)$", line)
        if bullet:
            line = bullet.group(1).strip()
        line = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", lambda match: match.group(1) or match.group(2) or "", line)
        line = line.replace("`", "").strip()
        if line and line != "[Candidate]":
            sections[current].append(("• " if bullet else "") + line)
    return {name: values for name, values in sections.items() if values}


def _render_draft_resume(document: Document, draft_content: str) -> bool:
    sections = _draft_sections(draft_content)
    if len(sections) < 2 or not ({"Core Skills", "Professional Experience", "Projects", "Education"} & sections.keys()):
        return False
    for section_name, lines in sections.items():
        _section_heading(document, section_name)
        for line in lines:
            paragraph = document.add_paragraph()
            is_bullet = line.startswith("• ")
            _compact_paragraph(paragraph, after=0, line_spacing=0.88)
            if is_bullet:
                paragraph.paragraph_format.left_indent = Inches(0.18)
                paragraph.paragraph_format.first_line_indent = Inches(-0.18)
            _set_run_font(paragraph.add_run(line))
    return True


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


def _relevance_terms(profile: dict[str, Any], job: Any, source_text: str = "") -> list[str]:
    """Return safe ranking terms without adding any candidate facts.

    The old ranking only considered saved profile skills and title words. A
    role can mention a source-resume technology in a different section of the
    posting, so this also promotes source terms that are actually present in
    the posting. Generic prose words are excluded to keep the ordering useful.
    """
    skills = [_text(item).casefold() for item in profile.get("skills", []) if _text(item)]
    title_words = re.findall(r"[a-z][a-z+#.-]{3,}", _text(getattr(job, "title", "")).casefold())
    job_text = f"{_text(getattr(job, 'title', ''))} {_text(getattr(job, 'description', ''))}".casefold()
    generic = {
        "this", "that", "with", "from", "have", "will", "your", "they", "their", "into", "about",
        "work", "role", "team", "build", "building", "using", "used", "experience", "strong", "looking",
        "including", "required", "requirements", "ability", "across", "through", "based", "systems", "data",
        "system", "service", "services", "time", "real", "production", "develop", "developed", "design",
    }
    source_terms = []
    for candidate in re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{3,}", source_text):
        normalized = candidate.casefold()
        if normalized not in generic and normalized in job_text:
            source_terms.append(normalized)
    return list(dict.fromkeys(sorted(skills + title_words + source_terms, key=len, reverse=True)))


def _relevance_score(value: str, terms: list[str], job_description: str) -> int:
    lower = value.casefold()
    job_lower = job_description.casefold()
    return sum(1 for term in terms if term in job_lower and term in lower)


def _set_run_font(run, size: float | None = None, bold: bool = False, italic: bool = False) -> None:
    # Let the document's Normal style provide the font. This keeps the default
    # resume Times New Roman while allowing a registered Word template to supply
    # its own typeface and body size.
    if size is not None:
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


def _content_width(document: Document) -> float:
    section = document.sections[0]
    return max(4.0, section.page_width.inches - section.left_margin.inches - section.right_margin.inches)


def _right_tab(paragraph, document: Document) -> None:
    paragraph.paragraph_format.tab_stops.add_tab_stop(Inches(_content_width(document)), WD_TAB_ALIGNMENT.RIGHT)


def _add_role(document: Document, record: dict[str, Any], terms: list[str], job_description: str) -> None:
    company = _text(record.get("company"))
    location = _text(record.get("location"))
    title = _text(record.get("title"))
    dates = " – ".join(part for part in (_text(record.get("start_date")), _text(record.get("end_date"))) if part)

    heading = document.add_paragraph()
    _compact_paragraph(heading, before=1, after=0, line_spacing=0.88)
    heading.paragraph_format.keep_with_next = True
    _right_tab(heading, document)
    _set_run_font(heading.add_run("• "))
    _set_run_font(heading.add_run(company), bold=True)
    if location:
        _set_run_font(heading.add_run(f"\t{location}"))

    role_line = document.add_paragraph()
    _compact_paragraph(role_line, after=0, line_spacing=0.86)
    role_line.paragraph_format.keep_with_next = True
    role_line.paragraph_format.left_indent = Inches(0.15)
    _right_tab(role_line, document)
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
    _right_tab(school_line, document)
    _set_run_font(school_line.add_run("• "))
    _set_run_font(school_line.add_run(_text(record.get("school"))), bold=True)
    if _text(record.get("location")):
        _set_run_font(school_line.add_run(f"\t{_text(record.get('location'))}"))

    degree_line = document.add_paragraph()
    _compact_paragraph(degree_line, after=0, line_spacing=0.86)
    degree_line.paragraph_format.left_indent = Inches(0.15)
    _right_tab(degree_line, document)
    _set_run_font(degree_line.add_run(_text(record.get("degree"))), italic=True)
    dates = " – ".join(part for part in (_text(record.get("start_date")), _text(record.get("end_date"))) if part)
    if dates:
        _set_run_font(degree_line.add_run(f"\t{dates}"), italic=True)


def build_resume_docx(
    profile: dict[str, Any],
    job: Any,
    draft_content: str,
    source_text: str = "",
    template_bytes: bytes | None = None,
) -> bytes:
    document = Document(io.BytesIO(template_bytes)) if template_bytes else Document()
    section = document.sections[0]
    if template_bytes:
        # Keep the template's page setup, headers, footers, theme, and styles;
        # clear sample body content before inserting candidate-specific text.
        body = document._element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)
    else:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.38)
        section.bottom_margin = Inches(0.38)
        section.left_margin = Inches(0.55)
        section.right_margin = Inches(0.55)
        section.header_distance = Inches(0.2)
        section.footer_distance = Inches(0.2)

    normal = document.styles["Normal"]
    if not template_bytes:
        normal.font.name = "Times New Roman"
        normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        normal.font.size = Pt(BODY_SIZE)
    elif normal.font.name:
        normal._element.rPr.rFonts.set(qn("w:eastAsia"), normal.font.name)
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

    job_description = _text(getattr(job, "description", ""))
    terms = _relevance_terms(profile, job, source_text)
    if not _render_draft_resume(document, draft_content):
        summary = _draft_summary(draft_content)
        if summary:
            _section_heading(document, "Professional Summary")
            summary_paragraph = document.add_paragraph()
            _compact_paragraph(summary_paragraph, after=1, line_spacing=0.9)
            _set_run_font(summary_paragraph.add_run(summary), size=BODY_SIZE)

        skills = _source_skills(source_text, profile)
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


def build_cover_letter_docx(profile: dict[str, Any], job: Any, content: str) -> bytes:
    """Render a reviewable one-page cover-letter draft with saved contact details."""
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.05

    name = _text(profile.get("preferred_name")) or _text(profile.get("name")) or "Candidate"
    contact = [
        _text(profile.get("location")),
        _text(profile.get("phone")),
        _text(profile.get("email")),
    ]
    title = _text(getattr(job, "title", "Target role"))
    company = _text(getattr(job, "company_name", ""))
    document.core_properties.title = f"{title} Cover Letter"
    document.core_properties.subject = f"Cover letter draft for {title} at {company}".strip()

    heading = document.add_paragraph()
    _set_run_font(heading.add_run(name), size=15, bold=True)
    _compact_paragraph(heading, after=2, line_spacing=1.0)
    contact_line = " | ".join(value for value in contact if value)
    if contact_line:
        paragraph = document.add_paragraph()
        _set_run_font(paragraph.add_run(contact_line), size=9.5)
        _compact_paragraph(paragraph, after=18, line_spacing=1.0)
    role_line = document.add_paragraph()
    _set_run_font(role_line.add_run(f"Re: {title} — {company}".rstrip(" —")), size=10.5, bold=True)
    _compact_paragraph(role_line, after=14, line_spacing=1.0)

    cleaned = re.sub(r"^\s*(?:#+\s*)?(?:cover letter(?: draft)?|application letter)\s*\n+", "", _text(content), flags=re.I)
    cleaned = re.sub(r"\n\s*\n\s*Review the claims.*$", "", cleaned, flags=re.I | re.S).strip()
    for block in re.split(r"\n\s*\n", cleaned):
        value = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not value:
            continue
        paragraph = document.add_paragraph()
        _set_run_font(paragraph.add_run(value), size=10.5)
        _compact_paragraph(paragraph, after=9, line_spacing=1.05)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
