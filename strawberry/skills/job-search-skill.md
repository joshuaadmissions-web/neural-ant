# Skill: Verified Agentic AI Job Search

## Goal
Find currently open U.S. agentic AI engineering vacancies that fit the user's private candidate profile and constraints. Report only new or materially changed matches.

## Inputs
Use the latest privately supplied candidate profile and preferences. Do not assume facts that are missing. If a hard filter cannot be evaluated (for example, salary or visa policy), label it unknown and exclude it when the user requires a verified match.

## Procedure
1. Read the saved candidate profile and the last report's deduplication log. Keep these private.
2. Search employer career sites and their official ATS listings for titles and close equivalents in agentic AI, AI agents, applied AI, LLM/agent platforms, and forward-deployed AI engineering. Expand to reputable public listings only to discover openings; verify each on an employer-controlled page.
3. Check the live page on the day of the run. Confirm the role is accepting applications, based in the United States or explicitly open to U.S. remote work, and not a duplicate of a previously reported opening.
4. Match the duties and required skills against candidate evidence. Do not treat a keyword match alone as fit.
5. Apply the user's current base salary minimum and experience range. Record the exact published compensation and experience requirement; distinguish base pay from total compensation. If salary is absent, do not imply it meets the floor.
6. Inspect the role's own text for sponsorship language. Exclude an explicit no-sponsorship statement. Otherwise use one of:
   - **Role-specific: stated** — the listing explicitly confirms sponsorship for this opening.
   - **Employer history only** — official or credible historical filing evidence exists; this is not a commitment for this opening.
   - **Unknown** — no reliable evidence found.
7. Save a private record of source URL, employer, requisition ID if present, checked date, and a concise change fingerprint. Use it only to deduplicate future reports.
8. Return only new or materially changed matches. A role is materially changed if its status, salary, location/work mode, sponsorship statement, or substantive requirements changed. If none qualify, state: “No new verified matches found.”

## Output
For each match, provide:
- Title and employer
- Location and remote/hybrid/on-site arrangement
- Published base salary (or “not published”)
- Experience requirement (or “not stated”)
- Sponsorship evidence, with role-specific wording separated from employer-history signals
- Date checked
- Direct employer/ATS listing link
- One short, evidence-based fit note tied to the candidate profile

## Do not
Do not apply, submit forms, upload files, contact employers, or complete attestations. Do not claim sponsorship from filing history alone. Do not report a job as open without checking its live employer-controlled page.
