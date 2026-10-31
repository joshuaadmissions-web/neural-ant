# Neural Ant supervised prototype — delivery report

Implementation delivered on 2026-10-31 for [NEU-2](/NEU/issues/NEU-2), the single approved implementation child of [NEU-1](/NEU/issues/NEU-1). CEO implemented directly; no agents were hired, no additional tasks created, and the initial delivery was a source archive. The prototype is now packaged under `supervised-prototype/` for GitHub publication; no app is deployed publicly.

## Delivered

- Local loopback-only Node app, with private persistent storage and untouched resume originals.
- TXT, Markdown, text-based PDF and DOCX upload; extracted-fact correction and explicit confirmation before matching.
- Configured Greenhouse and Lever public sources, timestamped source-check ledger, direct posting links, individual posting rechecks, open-status evidence, salary, location/work arrangement, experience and role-specific sponsorship evidence.
- Conservative U.S. engineer/developer role targeting, remote-first display, explicit annual USD base minimum of $100,000, unknown-salary separation, negative-sponsorship exclusions, confirmed-skill explanations and gaps.
- Visible Job Scout, Posting Verifier, Fit Reviewer, Resume Tailor and Application Prep Assistant task history with handoffs.
- Separate fact-preserving resume drafts, line-position change review, explicit review gate and download. No external AI requests.
- Manifest V3 Chrome extension: explicit Fill, Save and Restore; same-profile persistence, saved timestamps and return links, contact-field allowlist, empty-only writes, sensitive-field exclusions, local deletion.
- Controlled application fixture; reproducible unit, browser and live-source tests; synthetic screenshots and complete setup instructions.

## Run and install

Extract the source bundle, run `npm ci` and `npm start`, then open **http://127.0.0.1:4317**. Requires Node 22.13+; tested with Node 24.15. The app is not a public service and is not left running by the test suite.

In Chrome, open `chrome://extensions`, enable Developer mode, choose Load unpacked and select `extension/`. After changes, Reload the extension and refresh the application tab. Follow `README.md` for the full upload → confirm → check → review → export → Fill → Save → reopen → Restore → manual submission workflow.

## Test evidence

**Unit suite: 8 passed, 0 failed.** Raw output: `evidence/unit-tests.txt`.

**Controlled browser suite: 10 acceptance groups passed**, recorded 2026-10-31T17:35:45.558Z in `evidence/browser-results.json`:
- TXT upload, correction, confirmation gate, original byte preservation
- Fixture discovery, no-sponsorship exclusion, fit evidence, tailored change review and review gate
- Export includes contact allowlist only
- Extension Fill preserves existing email and sensitive answers, skips deceptive labels, legal fieldsets, uploads, and consent
- Saved draft storage contains only eligible contact answers; no sensitive values or tokens
- Browser profile restart retains draft, return link and status; Restore only fills empty eligible fields
- Delete local extension data clears profile and drafts
- No app browser JavaScript errors
- Cross-origin mutation and DNS-rebinding Host protections reject requests
- Local PDF and DOCX extraction, exact original preservation, confirmation and draft invalidation on new upload

All resume/profile/form data in tests and screenshots is synthetic. PDF/DOCX originals were compared byte-for-byte after extraction. Tests inspect saved extension storage to ensure sensitive fixture answers and hidden tokens are absent. They restart Chromium with the same profile before restoring, and verify preexisting answers remain untouched.

**Live public source validation**, recorded 2026-10-31T17:35:51.850Z in `evidence/live-sources.json`:
- Anthropic / greenhouse: ok, 675 published postings; checked 2026-10-31T17:35:50.496Z.
- Rigetti / lever: ok, 16 published postings; checked 2026-10-31T17:35:51.001Z.

Total 691 published records; 24 matched the title filter before candidate fit/eligibility review. Individual posting GETs were also checked for each provider. These are coverage counts, not qualifying-job recommendations for the real candidate. The default boards are a limited starting configuration; broader coverage requires adding known board slugs to `sources.json`.

## Boundaries and remaining limitations

This is a **validated controlled-form supervised prototype**, not a claim of live-site end-to-end readiness.

- Live employer application forms have not been filled or validated. Supported direct page patterns are Greenhouse numeric job pages and global Lever UUID job/apply pages. Embedded/custom domains, frames, shadow DOM, dropdowns, custom widgets, account flows and EU Lever remain manual.
- The browser harness uses a temporary extension copy with localhost-only test host permission and selects the fixture tab. The shipped manifest has only activeTab, scripting and storage. Its real toolbar-click permission gesture still needs a manual Chrome check.
- Parsing salary, location, sponsorship and experience uses conservative heuristics, not semantic guarantees. Unknowns remain unverified; users must inspect the original posting. Dollar amounts without explicit USD and annual base evidence are not qualifying salary matches. Employer sponsorship history is not researched or substituted for role evidence.
- “Open” means present in a public published-postings API at the recorded time. It does not guarantee the employer is still interviewing or that every application page works. Recheck immediately before applying.
- Scanned PDFs/images and legacy DOC are unsupported. Complex PDF layouts need careful correction. Tailoring preserves confirmed text and reorders facts; it is not generative rewriting or a formatted PDF resume.
- App data and extension data are local plaintext, protected by OS/Chrome profile access, not application encryption. `.private/`, contact exports and downloaded resumes must remain private. The shipped source archive contains none of that data.
- User must attach the correct resume, answer sensitive/legal questions, sign and submit manually. No accounts, submissions, authorization answers, saved credentials/files, CAPTCHA bypasses or external AI calls are implemented.

## Evidence and source files

`README.md` is the operator guide. `server.mjs`, `lib/`, `public/` and `extension/` are the implementation. `tests/` contains reproducible tests and synthetic upload fixtures. `evidence/` contains the raw results and screenshots. `package-lock.json` records exact dependency versions.

Integration references: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html) and [Lever Postings API](https://github.com/lever/postings-api).
