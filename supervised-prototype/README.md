# Neural Ant — private supervised prototype

A single-user local app and Chrome extension. All resume parsing, matching, and tailoring run locally. There is no AI-provider integration, telemetry, remote database, submission API, or deployment configuration. No agents are hired: the five visible roles are deterministic workflow tasks with an audit trail.

## Run locally

Requires Node.js 22.13+ (validated with Node 24.15), npm, and Chrome for the extension.

```sh
npm ci
npm start
```

Open **http://127.0.0.1:4317** (use this exact address, not `localhost`). The server listens only on loopback. Keep port 4317 for the controlled extension test form. Stop with Ctrl+C. State persists across restarts in `.private/`, which is ignored by Git. Do not expose this server through a tunnel or publish the workspace as a static site.

1. Upload TXT, Markdown, text-based PDF, or DOCX up to 5 MB. Scanned PDFs, images and legacy DOC are unsupported. PDF extraction is capped at 50 pages; complex columns/layouts can extract poorly. The original is stored by SHA-256 and downloadable byte-for-byte.
2. Correct the extracted name, contact fields, skills and every factual resume line. Enter verified professional years manually; the app does not infer experience from dates. Confirm using the checkbox and button. A new upload or reconfirmation invalidates previous drafts.
3. Click **Check configured public boards** for live sources, or **Load synthetic job fixtures** for a clearly labeled demonstration. Fixture results are never presented as live vacancies.
4. Inspect source checks, posting evidence, fit reasons and gaps. Click **Recheck posting** for an individual public API check immediately before preparation. A failed recheck makes open status unverified; a listing older than 24 hours cannot be a potential match.
5. Click **Prepare draft**, inspect the before/after line positions, then explicitly mark the draft reviewed. Drafts preserve the first two confirmed lines and reorder remaining confirmed lines by overlapping skills. They add no claims, and do not modify the original. Download the reviewed text draft and format it manually as needed.
6. Export the contact profile, import it into the extension, and open the direct application link. Follow the extension steps below. Review sensitive/legal questions yourself; attach the correct resume, sign and submit manually.

The app does not answer OPT, STEM OPT, H-1B, future sponsorship or work-authorization questions. Those questions remain entirely with the user. No real resume or job text is sent to an external AI provider; adding that capability would require separate permission.

## Source coverage and evidence

Edit `sources.json` to add a known public board slug. Restart is unnecessary; each scan reads the file. Defaults are **Anthropic / Greenhouse** and **Rigetti / Lever**. These demonstrate both integrations, not broad market coverage. No Google Jobs, LinkedIn, Indeed, Workday, Ashby or authenticated-site integration exists.

- Greenhouse: public `GET /v1/boards/{board}/jobs?content=true`, individual `GET /jobs/{id}`. Prospect posts are excluded. See [official documentation](https://docs.greenhouse.io/job-board.html).
- Lever: public global `GET /v0/postings/{board}?mode=json`, individual posting GET. EU API and forms are not integrated. The default list endpoint requests the published collection without a count limit; its returned count is recorded. See [official documentation](https://github.com/lever/postings-api).
- Every attempted board check records its timestamp, endpoint, count or failure. A fresh scan replaces the current job list, so failures cannot silently retain old matches. The last 100 source-check records are retained. Individual rechecks record results in the task trail.
- “Open” means present in the provider's published-postings API at the recorded time, not a guarantee the employer is still interviewing. Application-page availability, hidden closure notices, deadlines and redirects require manual review. Failed rechecks display unverified status rather than a confirmed open result.
- Roles target engineer/developer titles with AI, agent, LLM, cloud, backend or forward-deployed terms. Remote roles sort first; hybrid/on-site U.S. roles remain visible. Location and work arrangement are conservative text heuristics; unknown or ambiguous locations need review.
- Salary needs explicit annual USD **base** evidence and a lower bound of at least $100,000 to meet the requirement. A range spanning below $100,000 is below minimum. Currency-free dollar amounts, OTE, total compensation and unclear intervals remain unverified. Structured Lever annual USD ranges are only used when the description explicitly says base. Unverified jobs can be inspected but are never confirmed qualifying matches.
- Sponsorship evidence is drawn from the role text and shown verbatim in the local UI. Explicit negative sponsorship language is excluded by conservative patterns. Positive phrases are displayed as role statements; employer history is separately marked “not researched.” These heuristics can miss unusual phrasing and do not determine eligibility. Read the posting before proceeding.
- Fit is exact skill-term overlap against user-confirmed skills, plus simple experience-gap extraction. It is not a hiring probability, immigration decision, or proof of qualification. Unknown salary, U.S. location, sponsorship and experience are visible gaps. No candidate claims are populated from the task description.

The latest live check counts and timestamps are in `evidence/live-sources.json`. They are not a recommendation that any particular role qualifies for the real candidate.

## Chrome extension installation and use

1. Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**, and select the `extension/` folder from this project.
2. Pin Neural Ant. After changing code, click **Reload** on its extension card and refresh the application tab. Use one Chrome profile; local drafts do not sync to other profiles/devices.
3. In the local app, confirm resume facts and review a tailored draft. Click **Export contact profile**. Open the extension and import that JSON. The importer discards every non-allowlisted key. Delete the exported file from Downloads when you no longer need it.
4. On a supported application tab, click the extension toolbar icon, then **Fill empty fields**. Opening the popup grants Chrome's temporary active-tab access. There is no background filling or broad host permission.
5. Review the filled answers. Enter any additional eligible contact answers manually and click **Save eligible answers**. The extension shows a saved timestamp, eligible-field count, and a return link. A save replaces the prior snapshot for that application.
6. Close and reopen the browser in the same profile. Use the extension's return link; open the popup on that application tab and click **Restore empty fields**. Existing values, including whitespace, are preserved.
7. Complete everything else yourself. **Delete local profile & drafts** erases extension data when desired.

Supported direct pages:

| Host | Path |
| --- | --- |
| `boards.greenhouse.io` / `job-boards.greenhouse.io` | `/{board}/jobs/{numeric-id}` |
| `jobs.lever.co` | `/{board}/{uuid}` or `/{board}/{uuid}/apply` |
| `127.0.0.1:4317` | `/test-application` (synthetic only) |

Query strings and fragments are never saved. Greenhouse embedded/custom career sites, other hosts, account pages, EU Lever, iframes, shadow DOM, dropdowns, React widgets that ignore standard input events, and custom multi-step application state are unsupported. Normal React inputs receive native setter/input/change events, but employer-specific behavior has not been validated. Unsupported behavior yields zero fills or a supported-page message; complete those fields manually. Never attempt security bypasses.

Allowed fields are **full name, first name, last name, email, phone, location/city, LinkedIn URL, and website/portfolio URL**. They must be visible, enabled, editable text/email/tel/url inputs with an exact recognized label (or exact name/ID when unlabeled). Unknown labels are skipped even if an internal ID resembles an allowed field. Sensitive labels, descriptions and fieldset legends override the allowlist. Only HTTPS URLs without credentials, queries or fragments are retained as website values. No textarea/freeform answers are supported.

The extension never fills or stores authorization, sponsorship, visas, SSN, demographics, background checks, signatures, legal attestations/consents, passwords, tokens, uploaded files, security codes, or other sensitive/legal fields. It does not click submission buttons, create accounts, solve CAPTCHA or bypass verification. Saved drafts are restricted to validated contact values and a canonical public application URL.

## Privacy and storage

- Resume originals and app data live in `.private/` with restrictive filesystem modes; this is local plaintext, not encryption at rest. Use a trusted account and disk encryption. Stop the app and remove `.private/` to erase its profile, originals, job snapshots and drafts; this does not erase previously downloaded files.
- The app uses an HttpOnly, SameSite session cookie, exact Host validation, Origin validation for mutations, no-store headers, and a restrictive CSP. It is a local single-user prototype, not a hardened multi-user service. Users/processes with access to the operating-system account can access the files.
- Contact profiles and application drafts use `chrome.storage.local`, restricted to trusted extension contexts. They persist in the same Chrome profile. No credentials are requested. Local backups may include this data.
- Only configured public job-board GET requests go out during discovery. Board requests contain no resume/profile data. No profile is exposed through a public URL.
- Git ignores `.private`, environment files, dependency folders and logs. Only source code, synthetic fixtures and test evidence are published to GitHub; there is no public app deployment. Do not include private data or contact exports when sharing this source package.

## Tests and validation boundaries

```sh
npm test
npx playwright install chromium
npm run test:browser
npm run check:live
```

For a custom browser install directory, set `PLAYWRIGHT_BROWSERS_PATH` consistently for installation and browser tests. Browser tests use port 4317, an isolated temporary app store, a disposable Chrome profile, and synthetic data. Stop a running local app first. Dependencies are pinned in `package-lock.json`.

- Unit tests cover salary, sponsorship, fit gating, fact preservation, source constraints, skill boundaries, profile sanitization and canonical draft URLs.
- Browser tests cover TXT/PDF/DOCX intake and untouched originals, confirmation and review gates, fixture discovery, tailoring, export, real extension popup/injection/storage, sensitive exclusions, existing-value preservation, save/reopen/restore across a browser-profile restart, return links, local deletion, and origin/Host rejection.
- The browser harness copies the extension into a temporary directory and adds **test-only localhost host permission** to replace Chrome's toolbar activeTab gesture. It directs the popup at the fixture tab. The shipped manifest has no host permission. Production toolbar-click permission behavior still needs a manual Chrome check.
- Live validation covers read-only public listing and individual posting endpoints, separately from synthetic acceptance. **Live employer forms have not been filled or validated.** This is a tested controlled-form prototype, not a claim of universal or live-site end-to-end readiness.

Evidence: `evidence/unit-tests.txt`, `evidence/browser-results.json`, `evidence/live-sources.json`, and synthetic UI screenshots. No real candidate data is included.
