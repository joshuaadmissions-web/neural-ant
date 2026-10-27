# Neural Ant

> **A private AI command center for finding the right role, tailoring your story, and moving your career search forward.**

Neural Ant is a personal career-search workspace for organizing promising roles and preparing thoughtful, role-specific application materials. Its current prototype brings job discovery handoffs, role-fit review, application tracking, and writing support into one focused interface.

## What’s inside

- **Overview** — a snapshot of the job-search workspace and current pipeline.
- **Agent search handoff** — copies a structured search brief for use with a compatible browser agent, then imports matching job leads as JSON.
- **Job matcher** — reviews a pasted job description for profile keyword overlap and flags items to verify.
- **Application tracker** — organizes opportunities through shortlist, applied, interview, and decision stages.
- **AI copilot drafts** — creates starting points for resume tailoring, cover letters, recruiter outreach, and interview preparation.
- **Profile and backup** — keeps editable career preferences in the browser and exports a JSON backup.

## Run locally

The current app is a static HTML, CSS, and JavaScript prototype with no build step or server-side dependencies.

```bash
python3 -m http.server 4173 --directory dist
```

Open [http://localhost:4173](http://localhost:4173) in a browser.

## Privacy and data

Profile settings, imported job leads, and tracker entries are stored in the browser’s `localStorage` on the device where the app is used. Use **Export backup** in the app to save a copy. Clearing browser storage can remove the locally saved workspace. Do not use a shared browser profile for private job-search information.

The repository does not contain a resume upload service, cloud database, scheduled job-search worker, email integration, SMS integration, or automatic application submission. The agent-search handoff depends on the browser tool and account you choose to use; importing results is a separate step. The matcher’s score is a rough keyword-overlap indicator, not a hiring-probability estimate. Verify every resume claim, sponsorship signal, application answer, and job detail before relying on it.

## Repository layout

```text
.
├── .openai/hosting.json   # Neural Ant Sites project configuration
├── dist/
│   └── index.html         # App interface and client-side behavior
├── .gitignore
└── README.md
```

## Branches

- **`dev`** — ongoing development.
- **`test`** — changes prepared for review and verification.
- **`PROD`** — the approved production snapshot.

Promote changes from `dev` to `test`, then to `PROD` after review. Keep credentials, resumes, exported backups, and personal application data out of Git.

## Roadmap

- Add a secure resume intake and profile extraction flow.
- Add a hosted job-search worker and persistent job/application storage.
- Add reliable email interview notifications.
- Add sponsorship evidence and source links for each recommended employer and role.
- Add a review-first application workflow with explicit handling for employer attestations and verification steps.

---

**Neural Ant** · Your career search, with a little more intelligence and a lot more intention.
