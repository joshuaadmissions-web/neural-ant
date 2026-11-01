from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import smtplib
from threading import Event, Thread
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx
from docx import Document
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, create_engine, func, inspect, select, text as sql_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from api.docx_export import build_resume_docx


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("neural-ant")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/neural_ant.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgres://")
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgresql://")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/resumes"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "").strip()
APP_ENV = os.getenv("APP_ENV", "development").lower()
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
COOKIE_NAME = "neural_ant_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14
MAX_RESUME_BYTES = 10 * 1024 * 1024
DIST_DIR = Path(__file__).resolve().parent.parent / "dist"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
if DATABASE_URL.startswith("sqlite") and DATABASE_URL != "sqlite:///:memory:":
    Path(DATABASE_URL.removeprefix("sqlite:///" )).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
if APP_ENV == "production" and (len(SESSION_SECRET) < 32 or not os.getenv("NEURAL_ANT_PASSWORD")):
    raise RuntimeError("Production requires SESSION_SECRET (32+ characters) and NEURAL_ANT_PASSWORD.")
serializer = URLSafeTimedSerializer(SESSION_SECRET or "local-development-only-change-this", salt="neural-ant-session")


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ResumeRow(Base):
    __tablename__ = "resume"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    filename: Mapped[str] = mapped_column(String(255))
    file_key: Mapped[str] = mapped_column(String(1024))
    file_sha256: Mapped[str] = mapped_column(String(64))
    extracted_text: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SourceRow(Base):
    __tablename__ = "job_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ats_type: Mapped[str] = mapped_column(String(24), index=True)
    slug: Mapped[str] = mapped_column(String(160))
    company_name: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("ats_type", "slug", name="uq_source_type_slug"),)


class SponsorRow(Base):
    __tablename__ = "sponsor_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_key: Mapped[str] = mapped_column(String(255), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    evidence_type: Mapped[str] = mapped_column(String(80), default="public filing")
    evidence_url: Mapped[str] = mapped_column(String(2000))
    evidence_year: Mapped[str] = mapped_column(String(16), default="")
    filing_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    source: Mapped[str] = mapped_column(String(32))
    location: Mapped[str] = mapped_column(String(500), default="")
    work_mode: Mapped[str] = mapped_column(String(80), default="Unspecified")
    employment_type: Mapped[str] = mapped_column(String(120), default="Not stated")
    salary_text: Mapped[str] = mapped_column(String(255), default="Not stated")
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[str] = mapped_column(String(80), default="")
    fit_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    fit_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    fit_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sponsorship_status: Mapped[str] = mapped_column(String(40), default="unclear")
    sponsorship_evidence: Mapped[str] = mapped_column(Text, default="")
    sponsorship_url: Mapped[str] = mapped_column(String(2000), default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    applications: Mapped[list["ApplicationRow"]] = relationship(back_populates="job")


class ApplicationRow(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32), default="Shortlist")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    job: Mapped[JobRow] = relationship(back_populates="applications")


class DraftRow(Base):
    __tablename__ = "resume_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(160), default="local-match-draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AlertRow(Base):
    __tablename__ = "email_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_url: Mapped[str] = mapped_column(String(2000), unique=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "preferred_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "address_line1": "",
    "address_line2": "",
    "city": "",
    "state": "",
    "postal_code": "",
    "country": "",
    "current_company": "",
    "role": "",
    "linkedin_url": "",
    "github_url": "",
    "portfolio_url": "",
    "website_url": "",
    "skills": [],
    "education": "",
    "employment_history": [],
    "education_history": [],
    "certifications": [],
    "languages": [],
    "availability_date": "",
    "notice_period": "",
    "employment_type_preferences": [],
    "relocation_preference": "",
    "travel_preference": "",
    "target_titles": [],
    "location_preferences": ["United States"],
    "work_modes": ["Remote", "Hybrid", "On-site"],
    "minimum_salary": None,
    "years_experience": None,
    "work_authorization": "",
    "sponsorship_preferences": "",
    "summary": "",
    "email_alerts": False,
    "match_threshold": 50,
}

SUPPORTED_ATS = {"greenhouse", "lever", "ashby", "smartrecruiters", "adzuna", "usajobs"}
STAGES = {"Shortlist", "Applied", "Interview", "Decision", "Archived"}
SENSITIVE_HEADERS = {"host", "x-forwarded-host"}
try:
    SEARCH_INTERVAL_SECONDS = int(os.getenv("SEARCH_INTERVAL_SECONDS", "60" if APP_ENV == "development" else "0"))
except ValueError:
    SEARCH_INTERVAL_SECONDS = 0
SEARCH_INTERVAL_SECONDS = max(60, SEARCH_INTERVAL_SECONDS) if SEARCH_INTERVAL_SECONDS else 0
_search_stop = Event()
_search_thread: Thread | None = None


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_profile(db: Session) -> ProfileRow:
    row = db.get(ProfileRow, 1)
    if row is None:
        row = ProfileRow(id=1, data=DEFAULT_PROFILE.copy())
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def now_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def safe_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def canonical_job_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    tracking_keys = {"ref", "referrer", "source"}
    query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in tracking_keys]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urlencode(query), ""))


def parse_salary(text: str) -> tuple[int | None, int | None]:
    values: list[int] = []
    for raw, suffix in re.findall(r"\$\s*([\d,]+(?:\.\d+)?)\s*(k|m)?", text or "", re.I):
        try:
            number = float(raw.replace(",", ""))
            if suffix.lower() == "k":
                number *= 1000
            elif suffix.lower() == "m":
                number *= 1_000_000
            elif number < 1000:
                continue
            values.append(int(number))
        except ValueError:
            pass
    return (min(values), max(values)) if values else (None, None)


def infer_employment_type(title: str, description: str, explicit: str = "") -> str:
    """Return only employment-type signals stated in the supplied posting text."""
    text = " ".join(
        str(part) for part in (explicit, title, str(description or "")[:12000]) if part
    ).casefold()
    found: list[str] = []

    def positive(pattern: str) -> bool:
        match = re.search(pattern, text, re.I)
        if not match:
            return False
        prefix = text[max(0, match.start() - 28) : match.start()]
        return not re.search(r"(?:no|not|without|don't|do not|does not)\s*$", prefix, re.I)

    if positive(r"\b(?:corp(?:oration)?[- ]to[- ]corp(?:oration)?|c2c)\b"):
        found.append("C2C")
    if positive(r"\b(?:w[- ]?2|wage[- ]?2)\b"):
        found.append("W-2")
    if positive(r"\b1099\b"):
        found.append("1099")
    if positive(r"\bcontract[- ]?to[- ]?hire\b"):
        found.append("Contract-to-hire")
    elif positive(r"\b(?:contract(?:or|ual)?|temporary|temp[- ]to[- ]?hire)\b"):
        found.append("Contract")
    if positive(r"\bfull[- ]?time\b"):
        found.append("Full-time")
    if positive(r"\bpart[- ]?time\b"):
        found.append("Part-time")
    return " / ".join(dict.fromkeys(found)) or "Not stated"


def extract_resume_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        if suffix == ".docx":
            document = Document(io.BytesIO(data))
            parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            return "\n".join(parts).strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read this resume: {exc.__class__.__name__}") from exc
    raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")


MONTH_YEAR = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2}"
DATE_RANGE_RE = re.compile(
    rf"^(?P<label>.+?)\s+(?P<start>{MONTH_YEAR})\s*[–—-]\s*(?P<end>Present|Current|{MONTH_YEAR})$",
    re.I,
)


def _resume_lines(text: str) -> list[str]:
    return [
        re.sub(r"^[•·▪◦–—-]\s*", "", line.strip()).strip()
        for line in text.splitlines()
        if line.strip()
    ]


def _section(lines: list[str], heading: str, endings: tuple[str, ...]) -> list[str]:
    try:
        start = next(index for index, line in enumerate(lines) if line.casefold() == heading.casefold()) + 1
    except StopIteration:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].casefold() in {item.casefold() for item in endings}:
            end = index
            break
    return lines[start:end]


def _split_company_location(value: str) -> tuple[str, str]:
    match = re.search(r"(?P<location>[A-Za-z .'-]+,\s*(?:[A-Z]{2}|India|Canada|United States))$", value.strip())
    if not match:
        return value.strip(), ""
    company = value[:match.start()].strip(" ,")
    return company or value.strip(), match.group("location").strip()


def _parse_experience(lines: list[str]) -> list[dict[str, Any]]:
    date_indexes = [(index, DATE_RANGE_RE.match(line)) for index, line in enumerate(lines)]
    date_indexes = [(index, match) for index, match in date_indexes if match]
    records: list[dict[str, Any]] = []
    for position, (date_index, match) in enumerate(date_indexes):
        next_date_index = date_indexes[position + 1][0] if position + 1 < len(date_indexes) else len(lines)
        company_line = lines[date_index - 1] if date_index else ""
        company, location = _split_company_location(company_line)
        highlights = [line for line in lines[date_index + 1 : max(date_index + 1, next_date_index - 1)] if len(line) > 18]
        records.append({
            "company": company,
            "title": match.group("label").strip(),
            "start_date": match.group("start").strip(),
            "end_date": match.group("end").strip(),
            "location": location,
            "highlights": " ".join(highlights),
        })
    return [record for record in records if record["company"] and record["title"]]


def _parse_education(lines: list[str]) -> list[dict[str, Any]]:
    date_indexes = [(index, DATE_RANGE_RE.match(line)) for index, line in enumerate(lines)]
    date_indexes = [(index, match) for index, match in date_indexes if match]
    records: list[dict[str, Any]] = []
    for date_index, match in date_indexes:
        school_line = lines[date_index - 1] if date_index else ""
        school, location = _split_company_location(school_line)
        degree = re.sub(r"\s*;\s*GPA:.*$", "", match.group("label"), flags=re.I).strip()
        field = ""
        field_match = re.search(r"\s+in\s+(.+)$", degree, re.I)
        if field_match:
            field = field_match.group(1).strip()
            degree = degree[: field_match.start()].strip()
        records.append({
            "school": school,
            "degree": degree,
            "field": field,
            "start_date": match.group("start").strip(),
            "end_date": match.group("end").strip(),
            "location": location,
        })
    return [record for record in records if record["school"] and record["degree"]]


def extract_profile(text: str) -> dict[str, Any]:
    lines = _resume_lines(text)
    header = "\n".join(lines[:8])
    name = ""
    for line in lines[:8]:
        if 2 <= len(line) <= 72 and not re.search(r"@|https?://|\d{3}|resume|curriculum vitae", line, re.I):
            name = line
            break
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    phone_match = re.search(r"(?:\+?1[\s.-]*)?(?:\(?\d{3}\)?[\s.-]*)\d{3}[\s.-]*\d{4}", header)
    location_match = re.search(r"(?P<city>[A-Za-z][A-Za-z .'-]+),\s*(?P<state>[A-Z]{2})\b", header)
    postal_match = re.search(r"\b\d{5}(?:-\d{4})?\b", header)
    address_line1 = ""
    for line in lines[:8]:
        candidate = line.split("|")[0].strip()
        if re.search(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way)\b", candidate, re.I):
            address_line1 = candidate
            break
    linkedin_match = re.search(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/(?P<slug>[A-Za-z0-9_-]+(?:\s*-\s*[A-Za-z0-9_-]+)?)",
        header,
        re.I,
    )
    linkedin_url = ""
    if linkedin_match:
        slug = re.sub(r"\s+", "", linkedin_match.group("slug"))
        linkedin_url = f"https://linkedin.com/in/{slug}"

    skill_catalog = [
        "Python", "SQL", "RESTful API Design", "Microservices", "Terraform", "LLMs", "BERT", "Model Observability",
        "Feature Engineering", "Scikit-learn", "PyTorch", "AWS", "AWS Lambda", "ECS", "S3", "API Gateway", "Azure",
        "Azure DevOps", "Docker", "Kubernetes", "RabbitMQ", "Kafka", "Spark Streaming", "Redis", "ActiveMQ",
        "GitHub Actions", "GitLab", "Agile/Scrum", "FHIR Interoperability", ".NET Core", "ASP.NET Core", "Spring Boot",
        "Boto3", "OpenSearch", "Pandas", "MLOps", "Machine Learning", "NLP", "CI/CD", "RAG", "LLM", "OpenAI",
        "FastAPI", "React", "PostgreSQL", "MongoDB", "LangChain", "Bedrock", "TensorFlow", "Java", "TypeScript",
        "JavaScript", "GCP", "Model Lifecycle", "NLP fine-tuning",
    ]
    normalized_text = re.sub(r"\s+", " ", text.casefold())
    skills = [skill for skill in skill_catalog if re.search(rf"(?<![a-z0-9]){re.escape(skill.casefold())}(?![a-z0-9])", normalized_text)]
    experience = _parse_experience(_section(lines, "Experience", ("Projects", "Education", "Skills")))
    education_history = _parse_education(_section(lines, "Education", ("Skills", "Experience", "Projects")))
    location = f"{location_match.group('city')}, {location_match.group('state')}" if location_match else ""
    profile: dict[str, Any] = {
        "name": name,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0).strip() if phone_match else "",
        "location": location,
        "address_line1": address_line1,
        "city": location_match.group("city").strip() if location_match else "",
        "state": location_match.group("state").strip() if location_match else "",
        "postal_code": postal_match.group(0) if postal_match else "",
        "country": "United States" if re.search(r"\b(?:United States|USA|U\.S\.A?\.)\b", header, re.I) else "",
        "linkedin_url": linkedin_url,
        "skills": skills,
        "employment_history": experience,
        "education_history": education_history,
    }
    if experience:
        profile["current_company"] = experience[0]["company"]
        profile["role"] = experience[0]["title"]
    if education_history:
        first = education_history[0]
        profile["education"] = " ".join(part for part in (first["degree"], first["field"], first["school"]) if part)
    return profile


def put_resume_file(file_key: str, filename: str, data: bytes) -> str:
    if GCS_BUCKET:
        from google.cloud import storage

        bucket = storage.Client().bucket(GCS_BUCKET)
        key = f"resumes/{file_key}/{Path(filename).name}"
        bucket.blob(key).upload_from_string(data, content_type="application/octet-stream")
        return f"gs://{GCS_BUCKET}/{key}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / file_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return str(destination)


def delete_resume_file(file_ref: str) -> None:
    if file_ref.startswith("gs://"):
        try:
            from google.cloud import storage

            bucket_name, _, key = file_ref[5:].partition("/")
            if not bucket_name or not key:
                raise ValueError("Invalid GCS object reference")
            storage.Client().bucket(bucket_name).blob(key).delete()
        except Exception:
            log.exception("Unable to delete resume object from cloud storage")
    else:
        try:
            Path(file_ref).unlink(missing_ok=True)
        except OSError:
            log.exception("Unable to delete local resume file")


def authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        return False
    try:
        session_data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return session_data.get("sub") == "owner"
    except (BadSignature, SignatureExpired):
        return False


def require_auth(request: Request) -> None:
    # Local single-user mode is bound to 127.0.0.1 by run-local.sh.
    # Keep authentication enabled for production deployments.
    if APP_ENV != "production":
        return
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Sign in to Neural Ant.")


def public_job_payload(job: JobRow) -> dict[str, Any]:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company_name,
        "location": job.location,
        "work_mode": job.work_mode,
        "employment_type": job.employment_type,
        "salary": job.salary_text,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "description": job.description[:12000],
        "url": job.url,
        "source": job.source,
        "posted_at": job.posted_at,
        "fit_score": job.fit_score,
        "fit_reasons": job.fit_reasons or [],
        "fit_breakdown": job.fit_breakdown or {},
        "sponsorship_status": job.sponsorship_status,
        "sponsorship_evidence": job.sponsorship_evidence,
        "sponsorship_url": job.sponsorship_url,
        "first_seen": now_iso(job.first_seen),
        "last_seen": now_iso(job.last_seen),
    }


def resume_filename(profile: dict[str, Any], job: JobRow) -> str:
    def token(value: Any, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_")
        return (cleaned[:80] or fallback)

    candidate = profile.get("preferred_name") or profile.get("name") or "Candidate"
    return f"{token(job.company_name, 'Company')}_{token(job.title, 'Role')}_{token(candidate, 'Candidate')}_Resume.docx"


def parse_greenhouse(slug: str, company: str, client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"https://boards-api.greenhouse.io/v1/boards/{quote(slug)}/jobs", params={"content": "true"})
    response.raise_for_status()
    rows = response.json().get("jobs", [])
    return [{
        "company": company, "title": row.get("title", ""), "url": row.get("absolute_url", ""),
        "location": (row.get("location") or {}).get("name", ""), "work_mode": "Unspecified",
        "description": row.get("content", ""), "posted_at": row.get("updated_at", ""),
        "employment_type": infer_employment_type(row.get("title", ""), row.get("content", "")),
        "salary_text": "Not stated", "source": "Greenhouse",
    } for row in rows]


def parse_lever(slug: str, company: str, client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"https://api.lever.co/v0/postings/{quote(slug)}", params={"mode": "json", "limit": 100})
    response.raise_for_status()
    rows = response.json()
    output = []
    for row in rows:
        categories = row.get("categories") or {}
        salary = row.get("salaryRange") or {}
        salary_text = row.get("salaryText") or "Not stated"
        if salary and (salary.get("min") or salary.get("max")):
            salary_text = f"{salary.get('currency', 'USD')} {salary.get('min', '')} - {salary.get('max', '')} {salary.get('interval', '')}".strip()
        output.append({
            "company": company, "title": row.get("text", ""), "url": row.get("hostedUrl", ""),
            "location": categories.get("location", ""), "work_mode": row.get("workplaceType") or "Unspecified",
            "description": row.get("descriptionPlain", ""), "posted_at": str(row.get("createdAt", "")),
            "employment_type": infer_employment_type(row.get("text", ""), row.get("descriptionPlain", ""), categories.get("commitment", "")),
            "salary_text": salary_text, "source": "Lever",
        })
    return output


def parse_ashby(slug: str, company: str, client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{quote(slug)}", params={"includeCompensation": "true"})
    response.raise_for_status()
    rows = response.json().get("jobs", [])
    output = []
    for row in rows:
        comp = row.get("compensation") or {}
        salary_text = comp.get("scrapeableCompensationSalary") or comp.get("compensationTierSummary") or "Not stated"
        output.append({
            "company": company, "title": row.get("title", ""), "url": row.get("jobUrl", ""),
            "location": row.get("location", ""), "work_mode": "Remote" if row.get("isRemote") else "Unspecified",
            "description": row.get("descriptionPlain", ""), "posted_at": row.get("publishedAt", ""),
            "employment_type": infer_employment_type(row.get("title", ""), row.get("descriptionPlain", ""), str(row.get("employmentType") or row.get("employmentTypeName") or "")),
            "salary_text": salary_text, "source": "Ashby",
        })
    return output


def parse_smartrecruiters(slug: str, company: str, client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"https://api.smartrecruiters.com/v1/companies/{quote(slug)}/postings", params={"limit": 100, "offset": 0})
    response.raise_for_status()
    rows = response.json().get("content", [])
    output = []
    for row in rows:
        location = row.get("location") or {}
        location_text = ", ".join(str(part).strip() for part in (location.get("city"), location.get("region"), location.get("country")) if str(part).strip())
        posting_id = row.get("id") or row.get("uuid") or row.get("refNumber")
        url = row.get("postingUrl") or row.get("jobAdUrl") or (f"https://jobs.smartrecruiters.com/{quote(slug)}/{quote(str(posting_id))}" if posting_id else "")
        employment = (row.get("typeOfEmployment") or {}).get("label", "") if isinstance(row.get("typeOfEmployment"), dict) else ""
        output.append({
            "company": company, "title": row.get("name", ""), "url": url,
            "location": location.get("fullLocation") or location_text, "work_mode": "Remote" if location.get("remote") else ("Hybrid" if location.get("hybrid") else "Unspecified"),
            "description": str(row.get("jobAd", "")) if row.get("jobAd") else str(row),
            "posted_at": row.get("releasedDate", ""), "employment_type": infer_employment_type(row.get("name", ""), str(row), employment),
            "salary_text": "Not stated", "source": "SmartRecruiters",
        })
    return output


def _source_parts(slug: str, minimum: int = 2) -> list[str]:
    parts = [part.strip() for part in slug.split("|", 2)]
    if len(parts) < minimum or any(not part for part in parts[:minimum]):
        raise RuntimeError("Source slug must use the documented pipe-separated format.")
    return parts


def parse_adzuna(slug: str, company: str, client: httpx.Client) -> list[dict[str, Any]]:
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        raise RuntimeError("ADZUNA_APP_ID and ADZUNA_APP_KEY are required for Adzuna.")
    country, query, *location = _source_parts(slug)
    params = {"app_id": app_id, "app_key": app_key, "what": query, "results_per_page": 50, "content-type": "application/json"}
    if location and location[0]:
        params["where"] = location[0]
    response = client.get(f"https://api.adzuna.com/v1/api/jobs/{quote(country)}/search/1", params=params)
    response.raise_for_status()
    rows = response.json().get("results", [])
    return [{
        "company": (row.get("company") or {}).get("display_name") or company, "title": row.get("title", ""), "url": row.get("redirect_url", ""),
        "location": ((row.get("location") or {}).get("display_name", "")), "work_mode": "Unspecified", "description": row.get("description", ""),
        "posted_at": row.get("created", ""), "employment_type": infer_employment_type(row.get("title", ""), row.get("description", ""), row.get("contract_type", "")),
        "salary_text": f"{row.get('salary_min')} - {row.get('salary_max')} {row.get('salary_currency', '')}".strip(" -") if row.get("salary_min") or row.get("salary_max") else "Not stated", "source": "Adzuna",
    } for row in rows]


def parse_usajobs(slug: str, company: str, client: httpx.Client) -> list[dict[str, Any]]:
    api_key = os.getenv("USAJOBS_API_KEY", "").strip()
    user_agent = os.getenv("USAJOBS_USER_AGENT", "").strip()
    if not api_key or not user_agent:
        raise RuntimeError("USAJOBS_API_KEY and USAJOBS_USER_AGENT are required for USAJOBS.")
    query, *location = _source_parts(slug)
    headers = {"Authorization-Key": api_key, "User-Agent": user_agent}
    params = {"Keyword": query, "ResultsPerPage": 100, "Page": 1}
    if location and location[0]:
        params["LocationName"] = location[0]
    response = client.get("https://data.usajobs.gov/api/Search", params=params, headers=headers)
    response.raise_for_status()
    rows = response.json().get("SearchResult", {}).get("SearchResultItems", [])
    output = []
    for item in rows:
        row = item.get("MatchedObjectDescriptor") or {}
        locations = row.get("PositionLocation") or []
        location_text = ", ".join(str((entry or {}).get("LocationName", "")).strip() for entry in locations if (entry or {}).get("LocationName"))
        salary_rows = row.get("PositionRemuneration") or []
        salary = salary_rows[0] if salary_rows else {}
        salary_text = "Not stated"
        if salary.get("MinimumRange") or salary.get("MaximumRange"):
            salary_text = f"${salary.get('MinimumRange', '')} - ${salary.get('MaximumRange', '')}"
        output.append({
            "company": row.get("OrganizationName") or company, "title": row.get("PositionTitle", ""), "url": row.get("PositionURI", ""),
            "location": location_text, "work_mode": "Unspecified", "description": row.get("UserArea", {}).get("Details", {}).get("JobSummary", "") if isinstance(row.get("UserArea"), dict) else "",
            "posted_at": row.get("PublicationStartDate", ""), "employment_type": infer_employment_type(row.get("PositionTitle", ""), str(row)),
            "salary_text": salary_text, "source": "USAJOBS",
        })
    return output


def sponsor_for(db: Session, company: str) -> SponsorRow | None:
    key = company_key(company)
    return db.scalar(select(SponsorRow).where(SponsorRow.company_key == key).order_by(SponsorRow.imported_at.desc()))


def score_job(job: dict[str, Any], profile: dict[str, Any], sponsor: SponsorRow | None) -> tuple[int, list[str], dict[str, Any], str, str, str]:
    title = str(job.get("title") or "")
    description = str(job.get("description") or "")
    text = f"{title} {description}".lower()
    title_text = title.lower()
    reasons: list[str] = []
    breakdown: dict[str, Any] = {}
    score = 0

    skills = [str(item).strip() for item in profile.get("skills", []) if str(item).strip()]
    skill_hits = [skill for skill in skills if skill.lower() in text]
    skill_missing = [skill for skill in skills if skill not in skill_hits]
    skill_score = min(42, round(42 * len(skill_hits) / max(1, min(len(skills), 8)))) if skills else 0
    score += skill_score
    if skill_hits:
        reasons.append("Matching skills: " + ", ".join(skill_hits[:8]))
    breakdown["skills"] = {
        "label": "Skills",
        "score": skill_score,
        "max": 42,
        "detail": (
            f"Matched: {', '.join(skill_hits[:6])}"
            + (f" · Missing or not stated: {', '.join(skill_missing[:4])}" if skill_missing else "")
            if skill_hits
            else ("No saved skills to compare" if not skills else "No saved skills found in the posting")
        ),
    }

    targets = [str(item).strip() for item in profile.get("target_titles", []) if str(item).strip()]
    title_hits = [target for target in targets if target.lower() in title_text]
    related_title = bool(targets and not title_hits and any(token in title_text for target in targets for token in target.lower().split() if len(token) > 3))
    title_score = 24 if title_hits else 10 if related_title else 0
    score += title_score
    if title_hits:
        reasons.append("Title matches target: " + title_hits[0])
    elif related_title:
        reasons.append("Title has related target-role terms")
    breakdown["title"] = {
        "label": "Target role",
        "score": title_score,
        "max": 24,
        "detail": f"Matched: {title_hits[0]}" if title_hits else ("Related title terms found" if related_title else "No saved target title match"),
    }

    min_salary = profile.get("minimum_salary")
    salary_min, salary_max = parse_salary(str(job.get("salary_text") or ""))
    salary_score = 0
    if min_salary and salary_max and salary_max >= int(min_salary):
        salary_score = 12
        reasons.append("Stated salary overlaps your minimum")
        salary_detail = "Stated range overlaps your saved minimum"
    elif min_salary and not salary_max:
        reasons.append("Salary not stated; check before applying")
        salary_detail = "Salary not stated; verify on the official posting"
    elif min_salary:
        salary_detail = "Stated range does not reach your saved minimum"
    else:
        salary_detail = "No minimum salary saved"
    score += salary_score
    breakdown["salary"] = {"label": "Salary", "score": salary_score, "max": 12, "detail": salary_detail}

    modes = [str(item).lower() for item in profile.get("work_modes", []) if str(item).strip()]
    mode_text = (str(job.get("work_mode") or "") + " " + str(job.get("location") or "") + " " + description[:2000]).lower()
    mode_hit = next((mode for mode in modes if mode in mode_text), None)
    mode_score = 10 if mode_hit else 0
    score += mode_score
    if mode_hit:
        reasons.append("Work mode signal: " + mode_hit)
    breakdown["work_mode"] = {"label": "Work mode", "score": mode_score, "max": 10, "detail": f"Matched: {mode_hit}" if mode_hit else ("No saved work-mode match" if modes else "No work-mode preference saved")}

    location_preferences = [str(item).strip() for item in profile.get("location_preferences", []) if str(item).strip()]
    loc = (str(job.get("location") or "") + " " + description[:1000]).lower()
    location_hit = next((place for place in location_preferences if place.lower() in loc), None)
    location_score = 8 if location_hit else 0
    score += location_score
    if location_hit:
        reasons.append("Location matches a saved preference")
    breakdown["location"] = {"label": "Location", "score": location_score, "max": 8, "detail": f"Matched: {location_hit}" if location_hit else ("No saved location match" if location_preferences else "No location preference saved")}

    employment_type = str(job.get("employment_type") or infer_employment_type(title, description))
    employment_preferences = [str(item).strip() for item in profile.get("employment_type_preferences", []) if str(item).strip()]
    employment_text = employment_type.lower()
    employment_hit = next((pref for pref in employment_preferences if pref.lower() in employment_text or (pref.lower() == "w2" and "w-2" in employment_text)), None)
    employment_score = 4 if employment_hit else 0
    score += employment_score
    if employment_hit:
        reasons.append("Employment type matches preference: " + employment_hit)
    breakdown["employment_type"] = {
        "label": "Employment type",
        "score": employment_score,
        "max": 4,
        "detail": f"Posting: {employment_type}" + (f" · Preference matched: {employment_hit}" if employment_hit else (" · No preference match" if employment_preferences else " · No preference saved")),
    }

    low = description.lower()
    negative = any(term in low for term in ["unable to sponsor", "will not sponsor", "cannot sponsor", "no visa sponsorship", "not provide sponsorship"])
    explicit = any(term in low for term in ["visa sponsorship available", "will sponsor", "sponsorship is available", "sponsor h-1b", "h-1b sponsorship"])
    sponsor_score = 0
    if negative:
        sponsor_status, sponsor_evidence, sponsor_url = "posting says no", "The posting contains a sponsorship restriction.", str(job.get("url") or "")
        sponsor_detail = "Posting contains a sponsorship restriction"
    elif explicit:
        sponsor_status, sponsor_evidence, sponsor_url = "posting mentions sponsorship", "Sponsorship wording found in this job posting; verify with the employer.", str(job.get("url") or "")
        sponsor_score = 4
        score += sponsor_score
        sponsor_detail = "Posting mentions sponsorship; verify the exact requirement"
    elif sponsor:
        sponsor_status = "employer filing history"
        sponsor_evidence = f"{sponsor.evidence_type}; {sponsor.evidence_year or 'year not stated'}; {sponsor.filing_count} filing(s). This is employer history, not a guarantee for this job."
        sponsor_url = sponsor.evidence_url
        sponsor_score = 4
        score += sponsor_score
        sponsor_detail = "Historical employer evidence only; not a promise for this role"
    else:
        sponsor_status, sponsor_evidence, sponsor_url = "unclear", "No employer-level evidence imported and no clear sponsorship statement found in the posting.", ""
        sponsor_detail = "No clear sponsorship statement found"
    breakdown["sponsorship"] = {"label": "Sponsorship signal", "score": sponsor_score, "max": 4, "detail": sponsor_detail}
    return min(100, score), reasons, breakdown, sponsor_status, sponsor_evidence, sponsor_url


def refresh_job_scores(db: Session, profile: dict[str, Any]) -> None:
    for job in db.scalars(select(JobRow)).all():
        raw = {
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "work_mode": job.work_mode,
            "employment_type": job.employment_type,
            "salary_text": job.salary_text,
            "url": job.url,
        }
        fit, reasons, breakdown, status, evidence, evidence_url = score_job(raw, profile, sponsor_for(db, job.company_name))
        experience_note = re.search(r"Experience stated in supplied role notes:\s*(.+)", job.description or "")
        if experience_note:
            reasons.append(f"Role experience stated: {experience_note.group(1).splitlines()[0].strip()}")
        job.fit_score = fit
        job.fit_reasons = reasons
        job.fit_breakdown = breakdown
        if job.source != "Manual":
            job.sponsorship_status = status
            job.sponsorship_evidence = evidence
            job.sponsorship_url = evidence_url


def send_email(to_address: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender or not to_address:
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_address
    message.set_content(body)
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                if os.getenv("SMTP_USERNAME"):
                    smtp.login(os.getenv("SMTP_USERNAME", ""), os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.ehlo()
                if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
                    smtp.starttls()
                    smtp.ehlo()
                if os.getenv("SMTP_USERNAME"):
                    smtp.login(os.getenv("SMTP_USERNAME", ""), os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(message)
        return True
    except Exception:
        log.exception("Email notification failed")
        return False


def run_search(db: Session) -> dict[str, Any]:
    profile = ensure_profile(db).data or DEFAULT_PROFILE
    sources = db.scalars(select(SourceRow).where(SourceRow.enabled.is_(True))).all()
    result = {"sources_checked": 0, "jobs_seen": 0, "jobs_saved": 0, "new_matches": 0, "alerts_sent": 0, "source_errors": []}
    if not sources:
        result["message"] = "Add a supported employer board or public job API source to begin searching."
        return result
    adapters = {
        "greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby,
        "smartrecruiters": parse_smartrecruiters, "adzuna": parse_adzuna, "usajobs": parse_usajobs,
    }
    client = httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "NeuralAnt/1.0 job-search"})
    try:
        for source in sources:
            result["sources_checked"] += 1
            try:
                rows = adapters[source.ats_type](source.slug, source.company_name, client)
            except Exception as exc:
                log.warning("Job source %s/%s failed: %s", source.ats_type, source.slug, exc.__class__.__name__)
                result["source_errors"].append({"company": source.company_name, "source": source.ats_type, "error": exc.__class__.__name__})
                continue
            for raw in rows:
                url = canonical_job_url(str(raw.get("url", "")).strip())
                title = str(raw.get("title", "")).strip()
                if not url.startswith("https://") or not title:
                    continue
                result["jobs_seen"] += 1
                existing = db.scalar(select(JobRow).where(JobRow.url == url))
                job_company = str(raw.get("company") or source.company_name).strip()[:255]
                sponsor = sponsor_for(db, job_company)
                fit, reasons, breakdown, status, evidence, evidence_url = score_job(raw, profile, sponsor)
                salary_min, salary_max = parse_salary(raw.get("salary_text", ""))
                if existing:
                    existing.last_seen = datetime.now(timezone.utc)
                    existing.company_name = job_company
                    existing.employment_type = str(raw.get("employment_type") or infer_employment_type(title, str(raw.get("description", ""))))[:120]
                    existing.fit_score = fit
                    existing.fit_reasons = reasons
                    existing.fit_breakdown = breakdown
                    existing.sponsorship_status = status
                    existing.sponsorship_evidence = evidence
                    existing.sponsorship_url = evidence_url
                    continue
                job = JobRow(
                    url=url, company_name=job_company, title=title, source=str(raw.get("source", source.ats_type)),
                    location=str(raw.get("location", ""))[:500], work_mode=str(raw.get("work_mode", "Unspecified"))[:80],
                    employment_type=str(raw.get("employment_type") or infer_employment_type(title, str(raw.get("description", ""))))[:120],
                    salary_text=str(raw.get("salary_text", "Not stated"))[:255], salary_min=salary_min, salary_max=salary_max,
                    description=re.sub(r"<[^>]+>", " ", str(raw.get("description", "")))[:40000],
                    posted_at=str(raw.get("posted_at", ""))[:80], fit_score=fit, fit_reasons=reasons, fit_breakdown=breakdown,
                    sponsorship_status=status, sponsorship_evidence=evidence, sponsorship_url=evidence_url,
                )
                db.add(job)
                try:
                    db.flush()
                except IntegrityError:
                    db.expunge(job)
                    continue
                result["jobs_saved"] += 1
                if fit >= int(profile.get("match_threshold") or 50):
                    result["new_matches"] += 1
                    if profile.get("email_alerts") and profile.get("email"):
                        already_sent = db.scalar(select(AlertRow).where(AlertRow.job_url == url))
                        if not already_sent:
                            body = (f"{title} — {job_company}\n\nFit score: {fit}%\n"
                                    f"Location: {job.location or 'Not stated'}\nWork mode: {job.work_mode}\n"
                                    f"Salary: {job.salary_text}\nSponsorship signal: {status}\n{evidence}\n\n{url}")
                            if send_email(profile["email"], f"Neural Ant match: {title} at {job_company}", body):
                                db.add(AlertRow(job_url=url))
                                result["alerts_sent"] += 1
        db.commit()
    finally:
        client.close()
    return result


def serialize_application(item: ApplicationRow) -> dict[str, Any]:
    return {
        "id": item.id, "stage": item.stage, "notes": item.notes, "created_at": now_iso(item.created_at),
        "job": public_job_payload(item.job),
    }


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ProfileBody(BaseModel):
    model_config = {"extra": "allow"}


class SourceBody(BaseModel):
    ats_type: str
    slug: str = Field(min_length=1, max_length=160)
    company_name: str = Field(min_length=1, max_length=255)


class ApplicationBody(BaseModel):
    job_id: int
    notes: str = Field(default="", max_length=8000)


class StageBody(BaseModel):
    stage: str
    notes: str | None = Field(default=None, max_length=8000)


class TailorBody(BaseModel):
    confirmed_resume_use: bool = False
    use_external_ai: bool = False


class ManualJobItem(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    company_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    location: str = Field(default="", max_length=500)
    work_mode: str = Field(default="Unspecified", max_length=80)
    employment_type: str = Field(default="Not stated", max_length=120)
    salary_text: str = Field(default="Not stated", max_length=255)
    experience_text: str = Field(default="", max_length=255)
    sponsorship_note: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=12000)


class ManualJobsBody(BaseModel):
    jobs: list[ManualJobItem] = Field(min_length=1, max_length=50)


app = FastAPI(title="Neural Ant", version="1.0.0", docs_url="/api/docs" if APP_ENV != "production" else None, redoc_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    origin = request.headers.get("origin", "")
    extension_origin = origin.startswith("chrome-extension://") and len(origin) > len("chrome-extension://")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/") and request.url.path not in {"/api/auth/login", "/api/internal/run-search"}:
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/") and not extension_origin:
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    if extension_origin and request.url.path == "/api/form-profile":
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.on_event("startup")
def initialize_database() -> None:
    global _search_thread
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    if "employment_type" not in columns:
        with engine.begin() as connection:
            connection.execute(sql_text("ALTER TABLE jobs ADD COLUMN employment_type VARCHAR(120) DEFAULT 'Not stated'"))
    if "fit_breakdown" not in columns:
        with engine.begin() as connection:
            connection.execute(sql_text("ALTER TABLE jobs ADD COLUMN fit_breakdown JSON DEFAULT '{}'"))
    with SessionLocal() as db:
        for job in db.scalars(select(JobRow)).all():
            if not job.employment_type or job.employment_type == "Not stated":
                inferred = infer_employment_type(job.title, job.description or "")
                if job.employment_type != inferred:
                    job.employment_type = inferred
        refresh_job_scores(db, ensure_profile(db).data or DEFAULT_PROFILE)
        db.commit()
    if SEARCH_INTERVAL_SECONDS and _search_thread is None:
        _search_stop.clear()
        _search_thread = Thread(target=automatic_search_loop, name="neural-ant-search", daemon=True)
        _search_thread.start()
        log.info("Automatic job search enabled every %s seconds", SEARCH_INTERVAL_SECONDS)


def automatic_search_loop() -> None:
    while not _search_stop.wait(SEARCH_INTERVAL_SECONDS):
        db = SessionLocal()
        try:
            result = run_search(db)
            log.info("Automatic job search checked %s sources, saw %s jobs, saved %s new jobs", result["sources_checked"], result["jobs_seen"], result["jobs_saved"])
        except Exception:
            log.exception("Automatic job search failed")
        finally:
            db.close()


@app.on_event("shutdown")
def stop_automatic_search() -> None:
    global _search_thread
    if _search_thread is None:
        return
    _search_stop.set()
    _search_thread.join(timeout=5)
    _search_thread = None


@app.get("/api/health")
def health():
    return {"ok": True, "service": "neural-ant"}


@app.get("/api/config")
def config():
    return {"password_configured": bool(os.getenv("NEURAL_ANT_PASSWORD")), "ai_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")), "email_configured": bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM")), "resume_storage": "gcs" if GCS_BUCKET else "local volume"}


@app.get("/api/session")
def session_status(request: Request):
    if APP_ENV != "production":
        return {"authenticated": True, "local_mode": True}
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Not signed in")
    return {"authenticated": True}


_login_attempts: dict[str, list[float]] = {}


@app.post("/api/auth/login")
def login(body: LoginBody, request: Request):
    expected = os.getenv("NEURAL_ANT_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Set NEURAL_ANT_PASSWORD in the server environment first.")
    client_ip = request.client.host if request.client else "unknown"
    import time

    attempts = [stamp for stamp in _login_attempts.get(client_ip, []) if time.time() - stamp < 300]
    if len(attempts) >= 10:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Wait a few minutes and retry.")
    attempts.append(time.time())
    _login_attempts[client_ip] = attempts
    if not hmac.compare_digest(body.password.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Password is incorrect.")
    response = JSONResponse({"authenticated": True})
    response.set_cookie(COOKIE_NAME, serializer.dumps({"sub": "owner"}), httponly=True, secure=APP_ENV == "production", samesite="strict", max_age=SESSION_MAX_AGE, path="/")
    _login_attempts.pop(client_ip, None)
    return response


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=APP_ENV == "production", samesite="strict")
    return response


@app.get("/api/profile")
def get_profile(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    row = ensure_profile(db)
    resume = db.get(ResumeRow, 1)
    return {"profile": {**DEFAULT_PROFILE, **(row.data or {})}, "resume": {"filename": resume.filename, "uploaded_at": now_iso(resume.uploaded_at)} if resume else None}


@app.get("/api/form-profile")
def get_form_profile(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    """Return only user-approved contact/profile fields for the local browser extension."""
    row = ensure_profile(db)
    data = {**DEFAULT_PROFILE, **(row.data or {})}
    return {
        "name": data.get("name", ""),
        "preferred_name": data.get("preferred_name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "location": data.get("location", ""),
        "address_line1": data.get("address_line1", ""),
        "address_line2": data.get("address_line2", ""),
        "city": data.get("city", ""),
        "state": data.get("state", ""),
        "postal_code": data.get("postal_code", ""),
        "country": data.get("country", ""),
        "current_company": data.get("current_company", ""),
        "current_role": data.get("role", ""),
        "linkedin_url": data.get("linkedin_url", ""),
        "github_url": data.get("github_url", ""),
        "portfolio_url": data.get("portfolio_url", ""),
        "website_url": data.get("website_url", ""),
        "years_experience": data.get("years_experience"),
        "skills": data.get("skills", []),
        "employment_history": data.get("employment_history", []),
        "education_history": data.get("education_history", []),
        "certifications": data.get("certifications", []),
        "languages": data.get("languages", []),
        "summary": data.get("summary", ""),
        "work_authorization": data.get("work_authorization", ""),
        "sponsorship_preferences": data.get("sponsorship_preferences", ""),
    }


@app.put("/api/profile")
def save_profile(body: ProfileBody, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    allowed = set(DEFAULT_PROFILE)
    values = {key: value for key, value in body.model_dump().items() if key in allowed}
    if "email" in values and values["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(values["email"])):
        raise HTTPException(status_code=422, detail="Enter a valid notification email address.")
    if "minimum_salary" in values and values["minimum_salary"] not in (None, ""):
        values["minimum_salary"] = int(values["minimum_salary"])
    for key in ("skills", "target_titles", "location_preferences", "work_modes"):
        if key in values and not isinstance(values[key], list):
            values[key] = [part.strip() for part in str(values[key]).split(",") if part.strip()]
    if "match_threshold" in values:
        values["match_threshold"] = max(50, min(100, int(values["match_threshold"])))
    row = ensure_profile(db)
    row.data = {**DEFAULT_PROFILE, **(row.data or {}), **values}
    row.updated_at = datetime.now(timezone.utc)
    refresh_job_scores(db, row.data)
    db.commit()
    return {"profile": row.data}


@app.post("/api/resume")
async def upload_resume(file: UploadFile = File(...), _: None = Depends(require_auth), db: Session = Depends(get_db)):
    filename = Path(file.filename or "resume").name
    if Path(filename).suffix.lower() not in {".pdf", ".docx"}:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")
    content = await file.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be 10 MB or smaller.")
    text = extract_resume_text(filename, content)
    if len(text) < 80:
        raise HTTPException(status_code=422, detail="Could not extract enough text. Try a text-based PDF or DOCX file.")
    file_key = uuid.uuid4().hex
    file_ref = put_resume_file(file_key, filename, content)
    existing = db.get(ResumeRow, 1)
    if existing:
        delete_resume_file(existing.file_key)
        existing.filename = filename
        existing.file_key = file_ref
        existing.file_sha256 = hashlib.sha256(content).hexdigest()
        existing.extracted_text = text
        existing.uploaded_at = datetime.now(timezone.utc)
    else:
        db.add(ResumeRow(id=1, filename=filename, file_key=file_ref, file_sha256=hashlib.sha256(content).hexdigest(), extracted_text=text))
    extracted = extract_profile(text)
    profile_row = ensure_profile(db)
    profile_data = {**DEFAULT_PROFILE, **(profile_row.data or {})}
    extracted_keys = (
        "name", "email", "phone", "location", "address_line1", "city", "state", "postal_code", "country", "linkedin_url", "skills",
        "current_company", "role", "education", "employment_history", "education_history",
    )
    for key in extracted_keys:
        if key == "skills" and extracted.get(key):
            profile_data[key] = list(dict.fromkeys([*(profile_data.get(key) or []), *extracted[key]]))
        elif extracted.get(key) and not profile_data.get(key):
            profile_data[key] = extracted[key]
    profile_row.data = profile_data
    refresh_job_scores(db, profile_data)
    db.commit()
    return {"filename": filename, "characters_extracted": len(text), "extracted_fields": extracted, "message": "Resume stored privately. Profile fields are filled only when the uploaded resume contains that information; review them in My profile before use."}


@app.delete("/api/resume")
def delete_resume(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    row = db.get(ResumeRow, 1)
    if row:
        delete_resume_file(row.file_key)
        db.delete(row)
        db.commit()
    return {"deleted": True}


@app.get("/api/sources")
def list_sources(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    rows = db.scalars(select(SourceRow).order_by(SourceRow.company_name)).all()
    return [{"id": row.id, "ats_type": row.ats_type, "slug": row.slug, "company_name": row.company_name, "enabled": row.enabled} for row in rows]


@app.post("/api/sources")
def add_source(body: SourceBody, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    ats_type = body.ats_type.lower().strip()
    slug = body.slug.strip()
    company = body.company_name.strip()
    if ats_type not in SUPPORTED_ATS:
        raise HTTPException(status_code=422, detail="Choose a supported employer board or public job API source.")
    pattern = r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}"
    if ats_type in {"adzuna", "usajobs"}:
        pattern = r"[A-Za-z0-9][A-Za-z0-9 .,_+|/-]{0,159}"
    if not re.fullmatch(pattern, slug):
        raise HTTPException(status_code=422, detail="Source configuration contains unsupported characters.")
    row = SourceRow(ats_type=ats_type, slug=slug, company_name=company)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That job board is already configured.") from exc
    db.refresh(row)
    return {"id": row.id, "ats_type": row.ats_type, "slug": row.slug, "company_name": row.company_name, "enabled": row.enabled}


@app.delete("/api/sources/{source_id}")
def remove_source(source_id: int, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    row = db.get(SourceRow, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found.")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@app.post("/api/sponsors/import")
async def import_sponsors(file: UploadFile = File(...), _: None = Depends(require_auth), db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a normalized CSV file.")
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV must be 5 MB or smaller.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from exc
    required = {"company_name", "evidence_url", "evidence_year", "filing_count"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=422, detail="CSV headers must include company_name,evidence_url,evidence_year,filing_count. Optional: evidence_type,notes.")
    imported = 0
    for item in reader:
        name = (item.get("company_name") or "").strip()
        url = (item.get("evidence_url") or "").strip()
        if not name or not url.startswith("https://"):
            continue
        key = company_key(name)
        existing = db.scalar(select(SponsorRow).where(SponsorRow.company_key == key, SponsorRow.evidence_year == (item.get("evidence_year") or "").strip(), SponsorRow.evidence_url == url))
        if existing:
            continue
        try:
            count = max(0, int(item.get("filing_count") or 0))
        except ValueError:
            count = 0
        db.add(SponsorRow(company_key=key, company_name=name, evidence_type=(item.get("evidence_type") or "public filing")[:80], evidence_url=url, evidence_year=(item.get("evidence_year") or "")[:16], filing_count=count, notes=(item.get("notes") or "")[:2000]))
        imported += 1
    db.commit()
    return {"imported": imported, "message": "Employer filing history is only a historical signal; it does not guarantee sponsorship for a specific role."}


@app.get("/api/sponsors")
def list_sponsors(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    rows = db.scalars(select(SponsorRow).order_by(SponsorRow.company_name)).all()
    return [{"company_name": row.company_name, "evidence_type": row.evidence_type, "evidence_url": row.evidence_url, "evidence_year": row.evidence_year, "filing_count": row.filing_count, "notes": row.notes} for row in rows]


@app.post("/api/search/run")
def search_now(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    return run_search(db)


@app.post("/api/internal/run-search")
def scheduled_search(x_cron_secret: str | None = Header(default=None), db: Session = Depends(get_db)):
    expected = os.getenv("CRON_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured.")
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise HTTPException(status_code=403, detail="Invalid scheduled-job credential.")
    return run_search(db)


@app.get("/api/jobs")
def get_jobs(min_score: int = 0, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    rows = db.scalars(select(JobRow).where(JobRow.fit_score >= max(0, min_score)).order_by(JobRow.fit_score.desc(), JobRow.first_seen.desc()).limit(300)).all()
    return [public_job_payload(row) for row in rows]


@app.post("/api/jobs/manual")
def import_manual_jobs(body: ManualJobsBody, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    """Import user-supplied postings for review and supervised application prep."""
    profile = ensure_profile(db).data or DEFAULT_PROFILE
    imported: list[dict[str, Any]] = []
    updated = 0
    for item in body.jobs:
        url = canonical_job_url(item.url)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise HTTPException(status_code=422, detail="Each role URL must be a valid HTTPS link.")
        description_parts = [item.description.strip()]
        if item.experience_text.strip():
            description_parts.append(f"Experience stated in supplied role notes: {item.experience_text.strip()}")
        description = "\n\n".join(part for part in description_parts if part)[:40000]
        employment_type = infer_employment_type(item.title, description, item.employment_type)
        raw = {
            "title": item.title.strip(),
            "description": description,
            "location": item.location.strip(),
            "work_mode": item.work_mode.strip() or "Unspecified",
            "employment_type": employment_type,
            "salary_text": item.salary_text.strip() or "Not stated",
            "url": url,
        }
        sponsor = sponsor_for(db, item.company_name.strip())
        fit, reasons, breakdown, status, evidence, evidence_url = score_job(raw, profile, sponsor)
        if item.experience_text.strip():
            reasons.append(f"Role experience stated: {item.experience_text.strip()}")
        if item.sponsorship_note.strip():
            evidence = (f"{evidence} " if evidence else "") + (
                f"User-provided sponsorship context: {item.sponsorship_note.strip()} "
                "Verify this against the official posting and employer."
            )
            evidence_url = url

        existing = db.scalar(select(JobRow).where(JobRow.url == url))
        if existing:
            existing.company_name = item.company_name.strip()
            existing.title = item.title.strip()
            existing.location = item.location.strip()
            existing.work_mode = item.work_mode.strip() or "Unspecified"
            existing.employment_type = employment_type
            existing.salary_text = item.salary_text.strip() or "Not stated"
            existing.salary_min, existing.salary_max = parse_salary(existing.salary_text)
            existing.description = description
            existing.source = "Manual"
            existing.fit_score = fit
            existing.fit_reasons = reasons
            existing.fit_breakdown = breakdown
            existing.sponsorship_status = status
            existing.sponsorship_evidence = evidence
            existing.sponsorship_url = evidence_url
            existing.last_seen = datetime.now(timezone.utc)
            updated += 1
            imported.append(public_job_payload(existing))
            continue

        salary_min, salary_max = parse_salary(raw["salary_text"])
        job = JobRow(
            url=url,
            company_name=item.company_name.strip(),
            title=item.title.strip(),
            source="Manual",
            location=item.location.strip(),
            work_mode=item.work_mode.strip() or "Unspecified",
            employment_type=employment_type,
            salary_text=raw["salary_text"],
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            posted_at="",
            fit_score=fit,
            fit_reasons=reasons,
            fit_breakdown=breakdown,
            sponsorship_status=status,
            sponsorship_evidence=evidence,
            sponsorship_url=evidence_url,
        )
        db.add(job)
        db.flush()
        imported.append(public_job_payload(job))
    db.commit()
    return {"imported": len(body.jobs) - updated, "updated": updated, "jobs": imported}


@app.post("/api/applications")
def create_application(body: ApplicationBody, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    job = db.get(JobRow, body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    existing = db.scalar(select(ApplicationRow).where(ApplicationRow.job_id == body.job_id))
    if existing:
        return serialize_application(existing)
    row = ApplicationRow(job_id=job.id, notes=body.notes.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_application(row)


@app.get("/api/applications")
def list_applications(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    rows = db.scalars(select(ApplicationRow).order_by(ApplicationRow.updated_at.desc())).all()
    return [serialize_application(row) for row in rows]


@app.get("/api/applications/{application_id}/resume")
def download_application_resume(application_id: int, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    application = db.get(ApplicationRow, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")
    resume = db.get(ResumeRow, 1)
    if not resume:
        raise HTTPException(status_code=409, detail="Upload a resume first.")
    profile = ensure_profile(db).data or DEFAULT_PROFILE
    draft = db.scalars(select(DraftRow).where(DraftRow.job_id == application.job_id).order_by(DraftRow.created_at.desc())).first()
    if not draft:
        draft = DraftRow(job_id=application.job_id, content=deterministic_tailor(resume.extracted_text, application.job, profile), model="local-match-draft")
        db.add(draft)
        db.commit()
        db.refresh(draft)
    draft_content = draft.content
    content = build_resume_docx(profile, application.job, draft_content, resume.extracted_text)
    filename = resume_filename(profile, application.job)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.patch("/api/applications/{application_id}")
def update_application(application_id: int, body: StageBody, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    if body.stage not in STAGES:
        raise HTTPException(status_code=422, detail="Choose a supported application stage.")
    row = db.get(ApplicationRow, application_id)
    if not row:
        raise HTTPException(status_code=404, detail="Application not found.")
    row.stage = body.stage
    if body.notes is not None:
        row.notes = body.notes.strip()
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_application(row)


def deterministic_tailor(resume_text: str, job: JobRow, profile: dict[str, Any]) -> str:
    """Create a readable, source-grounded tailoring brief for local mode.

    PDF extraction commonly splits one bullet across several lines. The old
    implementation displayed those fragments directly in Copilot, which made
    the tailoring output look broken and harder to review.
    """

    def clean(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"(?<=\w)\s*-\s*(?=[a-z])", "-", value)
        return re.sub(r"(?<=[A-Za-z0-9)])\s+([,;:%)])", r"\1", value)

    def source_blocks(value: str) -> list[str]:
        blocks: list[str] = []
        current = ""
        headings = {"skills", "experience", "projects", "education"}
        for raw in value.splitlines():
            line = clean(raw)
            if not line:
                continue
            bullet = re.match(r"^[•▪◦–—-]\s*(.+)$", line)
            if bullet:
                if current:
                    blocks.append(current)
                current = bullet.group(1).strip()
                continue
            is_heading = line.casefold() in headings
            is_role_or_school_date = bool(re.search(r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2}", line, re.I))
            if current and not is_heading and not is_role_or_school_date:
                current = f"{current} {line}".strip()
            else:
                if current:
                    blocks.append(current)
                    current = ""
                blocks.append(line)
        if current:
            blocks.append(current)
        return [block for block in blocks if len(block) >= 18]

    source = source_blocks(resume_text)
    profile_terms = [str(value).casefold() for value in profile.get("skills", []) if str(value).strip()]
    job_terms = [
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z+#./-]{3,}", f"{job.title} {job.description[:12000]}")
        if word.casefold() not in {
            "this", "that", "with", "from", "have", "will", "your", "they", "their", "into", "about",
            "work", "role", "team", "build", "building", "using", "used", "experience", "strong", "looking",
            "including", "required", "requirements", "ability", "across", "through", "based", "systems",
        }
    ]
    terms = list(dict.fromkeys(profile_terms + job_terms))

    def score(value: str) -> int:
        lower = value.casefold()
        return sum(1 for term in terms[:140] if len(term) >= 4 and term in lower)

    bullet_starters = (
        "Architected ", "Developed ", "Engineered ", "Implemented ", "Eliminated ", "Orchestrated ",
        "Designed ", "Collaborated ", "Authored ", "Leading ", "Standardized ", "Built ", "Utilized ",
    )
    bullets = [block for block in source if block.startswith(bullet_starters)]
    selected = sorted(bullets, key=score, reverse=True)[:18] or source[:12]
    matched_terms = [term for term in terms if any(term in line.casefold() for line in selected) and len(term) >= 4]
    matched_text = ", ".join(dict.fromkeys(matched_terms[:18]))
    return (
        f"# Tailoring brief — {job.title} at {job.company_name}\n\n"
        "Local mode only reorders and selects wording already present in your uploaded resume. It does not add employers, dates, tools, metrics, authorization details, or claims. Review the downloaded resume before using it.\n\n"
        "## Source facts to emphasize\n\n" + "\n".join(f"- {line}" for line in selected) +
        "\n\n## Match signals found in your source resume\n\n"
        + (f"- {matched_text}" if matched_text else "- No direct source phrase matched the posting; keep the baseline resume and verify the role manually.") +
        "\n\n## Manual checks before submission\n\n"
        "- Confirm every selected line is still accurate and complete.\n"
        "- Confirm the posting's work authorization, sponsorship, location, and employment type yourself.\n"
        "- Attach the downloaded resume yourself; Neural Ant does not upload or submit applications.\n"
    )


def external_tailor(resume_text: str, job: JobRow, profile: dict[str, Any]) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "")
    if not api_key or not model:
        raise HTTPException(status_code=503, detail="External AI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL, or use the local draft option.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    prompt = f"""Create an ATS-friendly resume draft tailored to this job. Only use facts present in the source resume. Never invent employers, dates, skills, metrics, degrees, or work authorization. Preserve the candidate's actual meaning. Mark any suggested gap or missing detail as a question instead of filling it in. Return Markdown and include a short 'Facts to verify' section.

PROFILE:
{json.dumps(profile, ensure_ascii=False)[:8000]}

JOB POSTING:
Title: {job.title}
Company: {job.company_name}
Description: {job.description[:12000]}

WRITING STYLE:
Write in plain, human English. Use short sentences, common words, and direct verbs. Avoid inflated language, buzzwords, keyword stuffing, and claims that are not supported by the source resume. Keep technical terms only when they are relevant to the role. Use clear sections: Professional Summary, Core Skills, Professional Experience, and Education.

SOURCE RESUME:
{resume_text[:20000]}
"""
    try:
        response = httpx.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json={"model": model, "temperature": 0.2, "messages": [{"role": "system", "content": "You are a careful resume editor. Never fabricate candidate facts."}, {"role": "user", "content": prompt}]}, timeout=60)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return str(content), model
    except httpx.HTTPError as exc:
        log.exception("Configured AI provider call failed")
        raise HTTPException(status_code=502, detail="The configured AI provider could not complete this draft.") from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="The configured AI provider returned an unexpected response.") from exc


@app.post("/api/jobs/{job_id}/tailor")
def tailor_resume(job_id: int, body: TailorBody, _: None = Depends(require_auth), db: Session = Depends(get_db)):
    if not body.confirmed_resume_use:
        raise HTTPException(status_code=400, detail="Confirm that Neural Ant may use your stored resume to prepare this draft.")
    resume = db.get(ResumeRow, 1)
    if not resume:
        raise HTTPException(status_code=409, detail="Upload a resume first.")
    job = db.get(JobRow, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    profile = ensure_profile(db).data or DEFAULT_PROFILE
    if body.use_external_ai:
        content, model = external_tailor(resume.extracted_text, job, profile)
    else:
        content, model = deterministic_tailor(resume.extracted_text, job, profile), "local-match-draft"
    draft = DraftRow(job_id=job.id, content=content, model=model)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {"id": draft.id, "content": draft.content, "model": draft.model, "created_at": now_iso(draft.created_at), "warning": "Draft only. Review every claim and submit applications yourself."}


@app.get("/api/drafts")
def list_drafts(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    rows = db.scalars(select(DraftRow).order_by(DraftRow.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "job_id": row.job_id, "content": row.content, "model": row.model, "created_at": now_iso(row.created_at)} for row in rows]


@app.get("/api/status")
def status(_: None = Depends(require_auth), db: Session = Depends(get_db)):
    return {
        "database": "connected",
        "resume_uploaded": db.get(ResumeRow, 1) is not None,
        "job_sources": db.scalar(select(func.count(SourceRow.id))) or 0,
        "sponsor_records": db.scalar(select(func.count(SponsorRow.id))) or 0,
        "ai_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")),
        "email_configured": bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM")),
        "scheduled_search_configured": bool(os.getenv("CRON_SECRET")),
        "auto_search_interval_seconds": SEARCH_INTERVAL_SECONDS,
        "resume_storage": "private Google Cloud Storage bucket" if GCS_BUCKET else "private persistent volume",
    }


@app.get("/", include_in_schema=False)
def home():
    index = DIST_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=503, detail="Build the frontend with npm run build first.")
    return FileResponse(index)


if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="web")
