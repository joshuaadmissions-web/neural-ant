# Agent guidance for Neural Ant

## Project purpose
Neural Ant is a single-user job-search assistant. It discovers roles from configured public employer boards, scores fit, tracks opportunities, drafts role-specific resumes and cover letters, and leaves employer-form completion and submission to the user. Read [README.md](README.md) before changing behavior.

## Canonical job-search workflow
The user has designated [`ai-job-search`](https://github.com/ai-job-search-dev/ai-job-search) as the default workflow reference. Do not ask them to repeat this URL. The current local checkout is `/Users/josh/Documents/Codex/2026-11-06/le/work/ai-job-search`; the GitHub URL remains canonical if that path is unavailable. For workflow changes, read that repository's `.claude/commands/setup.md`, `scrape.md`, `rank.md`, and `apply.md`, plus the relevant skills. Neural Ant's mapping is in [docs/ai-job-search-workflow-parity.md](docs/ai-job-search-workflow-parity.md). Follow the repo's sequence and evidence rules, but state clearly where Neural Ant's deterministic app does not implement an agent step; never claim full parity when it is only an approximation.

## Working rules
- Treat this repository as the source of truth; inspect existing code and patterns before editing.
- Keep changes focused and explain assumptions in the final summary.
- Never commit resumes, extracted candidate profiles, contact details, credentials, cookies, tokens, database files, or job-search exports. Keep secrets in ignored local files or deployment secret managers.
- Do not invent candidate qualifications, employment dates, salary data, sponsorship policy, or job-posting facts.
- Treat H-1B/LCA filing history as historical employer-level evidence only. It does not prove sponsorship for a specific job or future eligibility.
- Do not submit job applications, send messages, accept legal terms, complete work-authorization attestations, or answer demographic questions on the candidate's behalf. Keep these actions under explicit user control.
- Leave work-authorization and sponsorship questions, legal attestations, demographic questions, and unverified role-specific answers to the user.
- AI processing of resume/profile/job text must remain opt-in and clearly disclosed.
- Keep local mode bound to loopback. Do not expose unauthenticated personal data endpoints to a network.
- Use official employer career pages as preferred listing sources; show source links and checked dates. Mark uncertainty instead of presenting guesses as facts.

## Project map
- `api/`: FastAPI service and persistence
- `src/`: web interface
- `scripts/`: build tooling
- `tests/`: automated checks (when present)

## Developer workflow
Follow the current README. Typical commands:
```bash
npm run build
python -m pip install -r requirements.txt
uvicorn api.main:app --env-file .env.local --reload --host 127.0.0.1 --port 8080
```

Before changing a feature, inspect its UI, API route, and persistence model as relevant. When the user asks for verification, run the narrowest relevant checks and report exactly what passed. Never claim a check was run if it was not.
