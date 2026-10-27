# Neural Ant

> **A private AI command center for finding the right role, tailoring your story, and moving your career search forward.**

Neural Ant is a single-user job-search application. It stores a resume and search profile in a private database, searches configured public employer career boards, ranks roles against your preferences, tracks applications, prepares resume drafts, and can email new-match alerts.

## Current capabilities

- Password-protected private workspace with HTTP-only session cookies.
- PDF/DOCX resume upload and basic profile extraction. Confirm extracted details before use.
- Persistent PostgreSQL storage (SQLite for local development); resume files use a private volume or optional private Google Cloud Storage bucket.
- Public job board search adapters for Greenhouse, Lever, and Ashby. You add employer board identifiers; this is not an all-platform aggregator.
- Match ranking by target titles, skill overlap, salary, work mode, and location.
- Optional CSV import of employer-level H-1B/LCA historical evidence. Historical filings do not establish that a company will sponsor a specific role.
- Reviewable resume drafts; optional external AI use requires a per-draft confirmation. The provider receives resume/profile/job text only after that confirmation.
- Application pipeline and email alerts for new matching listings.
- Authenticated scheduled-search endpoint so a hosted scheduler can run searches while your computer is off.

Neural Ant does not submit job applications or complete employer attestations. Keep every answer truthful and review tailored documents yourself.

## Run locally

Requirements: Docker and Docker Compose.

```bash
cp .env.example .env
```

Edit `.env` and set strong unique values for `NEURAL_ANT_PASSWORD`, `SESSION_SECRET`, `CRON_SECRET`, and `POSTGRES_PASSWORD`. Set `APP_ENV=production` when using HTTPS. Then start the service:

```bash
docker compose up --build -d
```

Open [http://localhost:8080](http://localhost:8080). Sign in with `NEURAL_ANT_PASSWORD`. Upload your resume in **My profile**, verify the extracted details, set your search preferences and notification email, then add employer boards under **Agent search**.

To stop the local service:

```bash
docker compose down
```

Your data remains in Docker volumes. To permanently remove local database and resume data, use `docker compose down -v` (destructive).

## Deployment for laptop-off operation

Deploy the container to an always-on host that supports Docker, PostgreSQL, persistent storage, and HTTPS. A small VM or container host is sufficient for one user. For Google Cloud Run, use managed PostgreSQL and a private GCS bucket for resumes; configure `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, database, and all secrets in the hosting provider’s secret manager. Do not use the container's local filesystem for persistent Cloud Run data.

Configure the host's scheduler (for example, Cloud Scheduler) to send an authenticated `POST` request to `/api/internal/run-search` at the cadence you want, with header `X-Cron-Secret: <CRON_SECRET>`. Never place the secret in frontend code or a public URL. Set HTTPS before `APP_ENV=production`; that enables secure session cookies.

Email is optional. Configure SMTP host, port, sender, credentials, and start-TLS settings. Interview schedules discovered in your email inbox are not yet parsed; notifications cover matching jobs only. SMS and automatic job applications are not included.

## Connect AI drafting (optional)

By default, Neural Ant creates a local draft that reorders existing resume lines. To use an OpenAI-compatible provider, set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` in the server secret configuration. The app asks for confirmation each time before sending resume, profile, and job text to that provider. Generated content remains a draft and must be checked against your resume.

## Search setup

Add a board by selecting its ATS and entering its public board slug and display name. For example, a career page hosted by `boards.greenhouse.io/acme` commonly uses `acme` as its board slug. Board formats can change; errors for a board are returned in the manual search result. The worker only searches the boards you configure, not LinkedIn, Indeed, or every job site.

The sponsorship CSV import expects UTF-8 with these headers:

```csv
company_name,evidence_url,evidence_year,filing_count,evidence_type,notes
Example Corp,https://example.gov/source,2025,12,LCA disclosure,Historical filing count
```

Use a normalized export from an official source. The app does not automatically fetch or refresh government disclosure files. A filing history is an employer-level historical signal, not a promise for any vacancy.

## Privacy and security

- The repository is public; never commit resumes, `.env`, credentials, or exported personal data.
- Resume file objects are stored outside the repository. Restrict the GCS bucket or host volume to this app's service identity.
- Use HTTPS and a long unique password. Add backups for the database and resume bucket before relying on the service.
- Configure SMTP and AI credentials only in the deployment secret manager, never in the browser.
- The API provides a single password login, an HTTP-only cookie, basic request security headers, and login throttling. For internet exposure, put it behind a reputable HTTPS reverse proxy and enable host-level rate limits and backups.
- Fit scores are ranking aids, not hiring predictions. Validate job details, compensation, authorization requirements, and sponsorship with the employer.

## Developer workflow

```bash
npm run build
python -m pip install -r requirements.txt
uvicorn api.main:app --reload --port 8080
```

The API documentation is available at `/api/docs` outside production mode. Frontend assets are built from `src/` into `dist/`.

## Branches

- `main` is the active development branch and default branch.
- `test` is available for staging changes.
- `PROD` is the release branch.

Keep personal profile data and secrets outside Git. GitHub Actions builds the frontend on pushes and pull requests.
