# Neural Ant matching research and product direction

This note records the product and research review used for the evidence-first matching changes.

## Similar products

- [Teal's Job Search Companion](https://chromewebstore.google.com/detail/teal-job-search-companion/opafjjlpbiaicbbgifbejoochmmeikep) combines job saving, company/contact tracking, multiple resume versions, and application tracking.
- [Huntr's Chrome extension](https://help.huntr.co/en/articles/9859408-the-huntr-chrome-extension) uses a saved profile to populate editable application fields and keeps the job in an application board.
- [Simplify](https://simplify.jobs/) describes a single profile, job matching, browser autofill, role-specific resume tailoring, and application tracking as one workflow.

Neural Ant already has the tracker, local resume drafts, a reusable profile, and a supervised extension. The missing product layer was an explanation of why a role received its score and which signals are still unknown.

## Research conclusions

- [Recommender system](https://en.wikipedia.org/wiki/Recommender_system) and [information retrieval](https://en.wikipedia.org/wiki/Information_retrieval) provide the right framing: retrieve a high-recall set first, then rank items against the user's information need. A single keyword count is not a complete recommendation system.
- [ConFit](https://arxiv.org/abs/2401.16349) and [ConFit v2](https://aclanthology.org/2025.findings-acl.661/) show the value of learned resume/job representations and hard negatives for ranking. Neural Ant does not yet have a labeled resume–job dataset, so shipping an unvalidated model would create false precision. The current step is a structured, inspectable baseline that can later produce feedback labels.
- [Human and LLM-Based Resume Matching](https://aclanthology.org/2025.findings-naacl.270/) reports that LLM scores have only minor correlation with human ratings and should not be treated as interchangeable. It supports showing dimensions and evidence instead of presenting one score as a hiring prediction.
- [Analyzing the Effects of a Human-in-the-Loop Candidate Recommendation Algorithm at Jobindex](https://doi.org/10.1145/3801092) supports keeping a person in the recommendation loop. Neural Ant therefore keeps opening the posting, legal questions, work authorization, signatures, and submission manual.
- [Evaluating Bias in LLMs for Job-Resume Matching](https://aclanthology.org/2025.naacl-industry.55/) and [Prompt Injection in Automated Résumé Screening](https://aclanthology.org/2026.findings-acl.142/) are reasons not to add hidden keyword stuffing, demographic inference, or self-promotional instructions to a resume. Tailoring must remain grounded in verified candidate evidence.

## Implemented direction

Each role now stores an explainable fit breakdown for:

- skills, including matched and missing-or-not-stated profile terms;
- target-role title match;
- salary overlap or unknown salary;
- work mode and location;
- employment-type preference, including Contract, Contract-to-hire, C2C, W-2, and 1099;
- sponsorship signal, clearly separating posting language from employer filing history.

The dashboard exposes the breakdown under **Why this fit**. Existing local jobs are backfilled when the app starts, and the result remains a ranking aid rather than a prediction of hiring or interview success.

## Next research-backed milestones

1. Capture explicit user feedback such as relevant, not relevant, saved, and applied; use it as private ranking data rather than silently training on applications.
2. Add freshness and duplicate controls so stale or repeated postings do not crowd out new roles.
3. Add optional semantic reranking only after a local evaluation set exists, comparing the structured baseline with an embedding model using Recall@K and nDCG@K.
4. Keep the browser assistant supervised: fill only supported empty fields and leave credentials, legal attestations, demographic questions, signatures, uploads, and submission to the user.
