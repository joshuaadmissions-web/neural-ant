# Neural Ant

> **A private AI command center for finding the right role, tailoring your story, and moving your career search forward.**

Neural Ant is a single-user job-search application. It stores a resume and search profile in a private database, searches configured public employer career boards, ranks roles against your preferences, tracks applications, prepares resume drafts, and can email new-match alerts.

## Current capabilities

- Local single-user workspace opens directly without a sign-in screen; production mode retains password protection.
- PDF/DOCX resume upload and basic profile extraction. Confirm extracted details before use.
- Persistent PostgreSQL storage (SQLite for local development); resume files use a private volume or optional private Google Cloud Storage bucket.
- Public job board search adapters for Greenhouse, Lever, and Ashby. You add employer board identifiers; this is not an all-platform aggregator.
- Match ranking by target titles, skill overlap, salary, work mode, and location.
- Optional CSV import of employer-level H-1B/LCA historical evidence. Historical filings do not establish that a company will sponsor a specific role.
- Reviewable resume drafts; optional external AI use requires a per-draft confirmation. The provider receives resume/profile/job text only after that confirmation.
- Application pipeline and email alerts for new matching listings.
- Authenticated scheduled-search endpoint so a hosted scheduler can run searches while your computer is off.
- Chrome extension prototype that saves visible application answers locally and restores them into empty fields when you reopen the same application page. Passwords and resume uploads are excluded; see [local draft behavior](docs/local-application-drafts.md).

## Product preview and free static hosting

A static Neural Ant workflow preview is in [`site/`](site/). It shows the four stages—discover roles, review fit, prepare a resume draft, and use the supervised Chrome assistant. It is a demonstration page only; it does not connect to the app, search jobs, or collect a resume.

To publish this preview for free with Cloudflare Pages:

1. In Cloudflare, open **Workers & Pages → Create → Pages → Connect to Git** and connect this repository.
2. Select the `main` branch.
3. Set **Root directory** to `site`, leave **Build command** empty, and set **Build output directory** to `.`.
4. Deploy. Pages gives you a public `pages.dev` URL and redeploys when you push changes to `main`.

Cloudflare currently lists a Free Pages allowance of 500 builds per month, up to 20,000 files per site, and 25 MiB per file. Check [current Pages limits](https://developers.cloudflare.com/pages/platform/limits/) before relying on the quotas.

This is static hosting only. It does not host Neural Ant's FastAPI API, database, resume files, or scheduled search. The complete app needs a private backend and persistent storage; see the cloud deployment section below. Keep resumes, profile exports, credentials, and private configuration out of `site/` and Git. See [site deployment notes](site/README.md).

Neural Ant does not submit job applications or complete employer attestations. Keep every answer truthful and review tailored documents yourself.

## Run locally on your Mac

Requirements: Python 3.10 or newer, Node.js 20 or newer, and npm. Docker is not required for local use.

1. Download or clone this repository and open Terminal in the `neural-ant` folder.
2. Start Neural Ant:

```bash
bash run-local.sh
```

On the first run, the script installs dependencies, builds the interface, and creates a local SQLite database. The resume and database are stored in the local `data/` directory; `.gitignore` keeps that folder and local secrets out of Git.

Open [http://127.0.0.1:8080](http://127.0.0.1:8080), then upload your resume in **My profile**. Verify the extracted profile and add employer boards under **Agent search**. To stop Neural Ant, return to Terminal and press **Ctrl+C**. Run `bash run-local.sh` again whenever you want to start it.

Local mode runs only while your Mac and the Terminal process are running. Searches will not run while the Mac is off or asleep. Your data stays on this Mac unless you explicitly configure an external AI provider; if you opt in to external AI drafting, resume and job text is sent to that provider.

For manual setup, copy `.env.local.example` to `.env.local`, set unique secrets if using scheduled searches, then run the build and Uvicorn commands described in the Developer workflow section.

## Low-cost cloud deployment (laptop off)

For a personal deployment, use Cloud Run for the app, Neon Free for PostgreSQL, Google Cloud Storage for the resume file, and Cloud Scheduler for the daily search. This avoids a paid Cloud SQL instance and keeps the existing PostgreSQL app architecture. The free quotas are usage limits, not a guaranteed $0 bill; configure billing alerts and check usage regularly.

### 1. Create the database in Neon

Create a free Neon project and copy its **pooled** connection string. Use the PostgreSQL connection string as `DATABASE_URL`; the app accepts `postgresql://` and automatically selects the psycopg driver. Keep this value private and store it in Google Secret Manager. Neon Free currently lists 100 compute-hours and 1 GB of database storage per project; the compute can scale to zero while idle. Review the provider's limits before relying on it.

### 2. Prepare the Google Cloud project

Choose `us-central1` (Iowa) for the Cloud Run service and resume bucket. Enable billing on the project, then enable Cloud Run, Cloud Build, Artifact Registry, Cloud Storage, Secret Manager, and Cloud Scheduler APIs. Create a private regional Cloud Storage bucket and a dedicated service account for Neural Ant. Grant that service account access to objects in this bucket only. Attach that identity to the Cloud Run service.

Set these values in Secret Manager or Cloud Run environment variables; do not commit them to Git:

- `APP_ENV=production`
- `DATABASE_URL` — the Neon pooled URL, stored as a secret
- `SESSION_SECRET` — random secret of at least 32 characters, stored as a secret
- `CRON_SECRET` — another random secret, stored as a secret
- `GCS_BUCKET` — the private bucket name
- `GOOGLE_CLOUD_PROJECT` — your Google Cloud project ID

Deploy the repository's Dockerfile as a Cloud Run service in `us-central1`, with password authentication enabled at the app layer, minimum instances set to zero, maximum instances set to one, and an appropriate memory limit such as 512 MiB or 1 GiB. Cloud Run supplies HTTPS and a service URL. The service account needs permission to access only the resume bucket. The app uses GCS for uploaded resume files when `GCS_BUCKET` is set; profile, job, and application records go to Neon.

### 3. Schedule job discovery

Create one Cloud Scheduler HTTP job to `POST https://YOUR-CLOUD-RUN-URL/api/internal/run-search` on the schedule you choose. Add header `X-Cron-Secret` with the same `CRON_SECRET`. This endpoint validates that secret; never put it in the URL or frontend. Cloud Scheduler supports authenticated Cloud Run targets; configure its service identity if using Cloud Run IAM authentication. Keep this as one scheduler job.

### 4. Add billing guardrails and verify

Set a small Cloud Billing budget alert before deploying. Budget alerts notify you but do not stop usage automatically. Cloud Run, Cloud Storage, Neon, and Scheduler each have free quotas and separate overage policies; exceed any provider's quota and charges may apply. Google Cloud lists free usage for Cloud Run, regional storage, and three Scheduler jobs per billing account; Neon lists its own limits. Check current provider pricing and actual usage after the first week.

After deployment, sign in, upload your resume, verify the extracted profile, configure employer boards, and run a manual search. Then confirm the scheduled run in logs and confirm email delivery if SMTP is configured. Do not upload a resume until you have reviewed where its file and extracted text are stored.

Google Cloud Run's local filesystem is temporary, so do not store the resume or database there. Cloud Run can scale to zero and still be reached at its HTTPS URL; the scheduled worker starts it when it runs.

Email is optional. Configure SMTP host, port, sender, credentials, and start-TLS settings. Interview schedules discovered in your email inbox are not yet parsed; notifications cover matching jobs only. SMS and automatic job applications are not included.

## Connect AI drafting (optional)

By default, Neural Ant creates a local draft that reorders existing resume lines. To use an OpenAI-compatible provider, set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` in the server secret configuration. The app asks for confirmation each time before sending resume, profile, and job text to that provider. Generated content remains a draft and must be checked against your resume.

## Navigate and fill application forms with browser RPA

The local Chrome extension provides a supervised browser workflow: from an employer job posting, it finds visible HTTPS links labeled for applying; you choose the correct link and open it in a new tab; on the application page, you click **Fill application** to fill supported empty fields from your saved Neural Ant profile. It does not click page buttons automatically, overwrite populated fields, upload a resume, or submit the application.

It checks visible field labels and current values locally to identify supported empty fields. It does not send form contents to Neural Ant or another service. It leaves work-authorization and sponsorship questions, unknown experience claims, referrals, legal attestations, demographic questions, and role-specific written answers for you. Attach the correct resume yourself and review the entire form before submitting.

1. Start Neural Ant with `bash run-local.sh` and open `http://127.0.0.1:8080`.
2. In **My profile**, upload your resume, verify the extracted profile, and save the details the extension may use.
3. In Chrome, open `chrome://extensions`, enable **Developer mode**, select **Load unpacked**, and choose this repository's `extension` folder. After an update, reload the extension and refresh job pages already open.
4. Open a job posting from Neural Ant or the employer's career site. Click the Neural Ant extension icon, choose **Find application links**, select the correct employer application link, and click **Open selected application**. Only visible HTTPS links are offered; the extension does not click page buttons.
5. On the application page, click the inline **Fill application** button or open the extension and choose **Fill this application**.
6. Review every answer, attach the tailored resume yourself, complete personal attestations yourself, and submit manually.

The extension fetches saved form-profile fields from Neural Ant at `127.0.0.1:8080` only after you click a fill action. Keep Neural Ant running locally. Chrome grants its content script access to HTTPS pages to detect application forms and inspect apply links when requested. The extension files are in `extension/`.

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
- Local mode has no sign-in because it listens only on your own computer (`127.0.0.1`). Do not change the bind address or expose it to a network. Production mode requires a unique password and HTTPS. Add backups for the database and resume bucket before relying on the service.
- Configure SMTP and AI credentials only in the deployment secret manager, never in the browser.
- Production mode provides password login, an HTTP-only cookie, basic request security headers, and login throttling. Local mode skips login and is intended only for the loopback interface.
- Fit scores are ranking aids, not hiring predictions. Validate job details, compensation, authorization requirements, and sponsorship with the employer.

## Developer workflow

```bash
npm run build
python -m pip install -r requirements.txt
uvicorn api.main:app --env-file .env.local --reload --host 127.0.0.1 --port 8080
```

The API documentation is available at `/api/docs` outside production mode. Frontend assets are built from `src/` into `dist/`.

## Branches

- `main` is the active development branch and default branch.
- `test` is available for staging changes.
- `PROD` is the release branch.

Keep personal profile data and secrets outside Git. GitHub Actions builds the frontend on pushes and pull requests.

## Use with Strawberry Companions

This repository includes a portable setup pack for a private Strawberry job-search companion. It guides research and reporting; it does not install a companion or configure a scheduled routine in Strawberry.

- [Companion setup and privacy notes](strawberry/README.md)
- [Companion brief](strawberry/companion-brief.md)
- [Verified job-search skill](strawberry/skills/job-search-skill.md)
- [Optional routine prompt](strawberry/routines/routine-prompt.md)

Keep your resume and candidate profile in Strawberry's private workspace. Do not commit them to this public repository. Run the search manually and review its results before enabling any recurring routine.
