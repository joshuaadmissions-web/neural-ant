# Deployment and local setup

This guide covers local development, the static preview, and a full private deployment. The static preview is not the application backend. Provider pricing, quotas, and dashboard steps can change, so verify them before deploying.

## Product preview and free static hosting

A static Neural Ant workflow preview is in [`site/`](site/). It shows the four stages—set up a profile, scrape public job sources, rank fit, and prepare a role-specific application pack. It is a demonstration page only; it does not connect to the app, search jobs, or collect a resume.

To publish this preview for free with Cloudflare Pages:

1. In Cloudflare, open **Workers & Pages → Create → Pages → Connect to Git** and connect this repository.
2. Select the `main` branch.
3. Set **Root directory** to `site`, leave **Build command** empty, and set **Build output directory** to `.`.
4. Deploy. Pages gives you a public `pages.dev` URL and redeploys when you push changes to `main`.

Check [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) before relying on a free allowance; quotas and plan terms can change.

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

Open [http://127.0.0.1:8080](http://127.0.0.1:8080), then upload your resume in **My profile**. Verify the extracted profile and add employer boards under **Agent search**. The dashboard shows roles at or above the saved match threshold, with a minimum display threshold of 50%. To stop Neural Ant, return to Terminal and press **Ctrl+C**. Run `bash run-local.sh` again whenever you want to start it.

The app is installable on a phone once it has an HTTPS cloud URL. On iPhone, open that URL in Safari and tap **Share → Add to Home Screen**; on Android, use Chrome's **Install** prompt or **Add to Home Screen** menu. A home-screen install opens the hosted app; it still needs the cloud backend and an internet connection for live profile and job data. A local `127.0.0.1` address on your Mac is not the phone's address.

Local mode runs only while your Mac and the Terminal process are running. Searches will not run while the Mac is off or asleep. Your data stays on this Mac unless you explicitly configure an external AI provider; if you opt in to external AI drafting, resume and job text is sent to that provider.

In local development, the automatic search interval defaults to 60 seconds. Set `SEARCH_INTERVAL_SECONDS` to a larger value in `.env.local` if a job board asks for a slower cadence. Hosted deployments should use the authenticated `/api/internal/run-search` scheduler endpoint instead of relying on an in-process loop.

For manual setup, copy `.env.local.example` to `.env.local`, set unique secrets if using scheduled searches, then run the build and Uvicorn commands described in the Developer workflow section.

## Low-cost cloud deployment (laptop off)

For a personal deployment, use Cloud Run for the app, Neon for PostgreSQL, Google Cloud Storage for the resume file, and Cloud Scheduler for the search schedule. This keeps the existing PostgreSQL app architecture without requiring Cloud SQL. It is not a guaranteed $0 deployment: check each provider's current pricing and quotas, configure billing alerts, and monitor usage.

### 1. Create the database in Neon

Create a Neon project on a plan that fits your usage and copy its **pooled** connection string. Use the PostgreSQL connection string as `DATABASE_URL`; the app accepts `postgresql://` and automatically selects the psycopg driver. Keep this value private and store it in Google Secret Manager. Check [Neon's current pricing and limits](https://neon.tech/pricing) before choosing a plan.

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

Set a Cloud Billing budget alert before deploying. Budget alerts notify you but do not stop usage automatically. Cloud Run, Cloud Storage, Neon, and Scheduler have separate prices and usage limits; charges may apply when you exceed a quota. Check current provider pricing before deploying and review actual usage after the first week.

After deployment, sign in, upload your resume, verify the extracted profile, configure employer boards, and run a manual search. Then confirm the scheduled run in logs and confirm email delivery if SMTP is configured. Do not upload a resume until you have reviewed where its file and extracted text are stored.

Google Cloud Run's local filesystem is temporary, so do not store the resume or database there. Cloud Run can scale to zero and still be reached at its HTTPS URL; the scheduled worker starts it when it runs.

Email is optional. Configure SMTP host, port, sender, credentials, and start-TLS settings. Interview schedules discovered in your email inbox are not yet parsed; notifications cover matching jobs only. SMS and automatic job applications are not included.

## Developer workflow

```bash
npm run build
python -m pip install -r requirements.txt
uvicorn api.main:app --env-file .env.local --reload --host 127.0.0.1 --port 8080
```

The API documentation is available at `/api/docs` outside production mode. Frontend assets are built from `src/` into `dist/`.
