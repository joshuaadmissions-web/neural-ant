# Neural Ant Companion Pack for Strawberry

This folder contains a setup brief and reusable workflows for Strawberry Companions. It is a **portable instruction pack**, not a Strawberry integration or a companion already installed in your account.

## Set up your private companion
1. In Strawberry, create a personal companion named **Neural Ant — Job Search**.
2. Give it the instructions in [companion-brief.md](companion-brief.md).
3. Add [job-search-skill.md](skills/job-search-skill.md) as a reusable skill (or paste its contents into the companion's skill editor).
4. Keep your resume and candidate profile in Strawberry's private workspace or attach them directly to a private companion chat. **Do not commit them to this public repository.**
5. Run the workflow manually once and review its sourcing, match decisions, and change log.
6. Only after the manual run is reliable, create a Strawberry routine using [routine-prompt.md](routines/routine-prompt.md). Configure its schedule in Strawberry itself and keep the review stop enabled.

Strawberry's current product describes companions as persistent agents with their own files, skills, and context, and supports scheduled routines. Verify the current UI labels in your installed version; they may change.

## Suggested first run
Ask: “Use the Neural Ant Job Search skill and my private candidate profile. Find currently open U.S. agentic AI engineering roles matching my criteria. Return only new or materially changed verified roles. Do not apply, submit, upload, or contact anyone.”

## Data boundary
The companion may read public job pages and the private candidate material you choose to attach. It should return source links, dates checked, and evidence. The repository itself should contain no candidate-specific personal information.
