# AI Job Search workflow mapping

This note maps the user's canonical [ai-job-search repository](https://github.com/ai-job-search-dev/ai-job-search) to Neural Ant. Keep that repository as the default workflow reference; do not ask the user to repeat the URL. Neural Ant keeps its own single-user UI, data model, and safety boundaries, so these are mapped app equivalents rather than direct execution of the repo's Markdown agent commands.

## End-to-end in Neural Ant

On the Chat page, upload a resume. Neural Ant extracts and saves the profile fields it can read. Click **Find & prepare jobs** to run the mapped scrape and rank steps, then prepare local resume and cover-letter drafts for up to five top-fit remote roles whose postings explicitly mention visa/H-1B sponsorship. Existing drafts are kept as-is. Employer-board fetches now run in parallel and their results are saved serially; the public index search runs alongside them. The resume and work-authorization details stay local; only the role query and filters go to the broad index. Sponsorship wording is a posting signal and must be confirmed for the exact role and petition. C2C is tracked separately. Review the prepared files under Applications, open official postings yourself, complete employer forms, and submit manually.

The button is not a direct runner for the repo's Markdown commands. Neural Ant does not yet dispatch the setup interview, separate posting-scorer and reviewer agents, company research, LaTeX PDF compilation, or visual PDF inspection. Its current apply equivalent is local, source-grounded draft generation plus a deterministic text check. Do not describe those steps as complete repo parity.

| Source workflow | Neural Ant workflow | Parity and limits |
| --- | --- | --- |
| `/setup` | My profile and resume upload | Profile extraction and corrections stay in the local Neural Ant database. |
| `/scrape` | Agent search | Searches configured public ATS boards and the Freehire public index, with recency filters and source health. It does not scrape LinkedIn or every aggregator. |
| `/rank` | Job matcher, fit score, sponsorship filter, posting-age and deadline signals | Results are ranked by profile fit and sponsorship evidence. Stale postings and closing dates are flagged. Neural Ant does not yet keep per-posting fetch retries, deadline expiry state, language/location vetoes, or the source repo's four-part reviewer scoring. A displayed date is a signal to check the official listing. |
| `/apply` | Prepare for review or use **Find & prepare jobs** | Saves a job-specific resume and cover letter, runs local source checks, reads back the generated DOCX text for keyword coverage, and offers an opt-in external draft → review → revision pass. The one-click flow uses local drafting for up to five top-fit remote roles with explicit sponsorship wording and leaves existing drafts unchanged. Neural Ant does not fetch company research, create a separate reviewer agent, render PDFs, or inspect page breaks automatically; inspect downloaded files yourself. |
| `/interview` | Interview prep within each tracked role | Produces a saved, stage-specific question and STAR pack from resume examples, job requirements, tracker notes, and latest prepared drafts. It does not fetch company research or assume that a prepared draft was submitted. |
| `/outcome` | Applications tracker and stale-role review | Stores stage, notes, outcome, and follow-up date; uses Done for submitted roles and excludes completed roles plus duplicate company/title listings from fresh searches; archives the posting and latest prepared-document snapshot; and offers a user-approved 60-day stale sweep. Up to two follow-up drafts are saved per role. Neural Ant does not infer that a draft was submitted. |
| `/gmail-sync` | Workflow tools → Review a Gmail message | Manual paste-and-preview only. There is no direct Gmail connection. The stage change is saved only after review. |
| `/html-report` | Download offline report | Self-contained report includes the tracker, fit and sponsorship signals, filters, and charts without resume/profile contact details. |
| `/notion-sync` | Download Notion-ready CSV | One-way manual import, not live Notion synchronization. |
| `/expand` | Workflow tools → Expand profile from public sources | Scans text the user pastes, stores source evidence, and waits for approval before adding suggested skills. Neural Ant does not fetch the supplied URL. |
| `/upskill` | AI Copilot → Skill-gap learning plan | Local checklist based on posting terms missing from the saved skills list; it does not assert that a skill is absent from the candidate's experience. |
| `/add-template` | Workflow tools → Custom resume templates | Supports Word `.docx` page setup and style reuse. It does not provide arbitrary LaTeX or custom compile toolchains. |
| `/add-portal` | Agent search → Public job source | Supports the built-in public ATS/API adapters. It does not generate and execute a new portal-specific CLI integration. |
| `/reset` | Workflow tools → Reset local workspace data | Typed confirmation is required for scoped deletion. |

Neural Ant does not open employer application pages automatically, upload documents to a portal, answer work-authorization or legal questions, send recruiter messages, or submit applications. The user chooses and reviews those actions.
