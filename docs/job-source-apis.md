# Job-source API coverage

Neural Ant now supports six source types:

- Greenhouse, Lever, and Ashby employer boards.
- SmartRecruiters public employer postings.
- Adzuna search API.
- USAJOBS search API.

These sources are configured individually because there is no single lawful public API that returns every job from LinkedIn, Indeed, Glassdoor, and all ATS products. The app does not create accounts, scrape authenticated pages, bypass CAPTCHAs, or reverse-engineer private endpoints.

## Configure in the local app

Open **Agent search** and choose a source type.

- **SmartRecruiters:** enter the company identifier used in its public SmartRecruiters URL. No app credential is stored by Neural Ant.
- **Adzuna:** set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in `.env.local`, then use `country|query|location`, for example `us|agentic ai engineer|remote`.
- **USAJOBS:** request an API key from USAJOBS, set `USAJOBS_API_KEY` and `USAJOBS_USER_AGENT` in `.env.local`, then use `query|location`, for example `artificial intelligence|Washington DC`.

Restart `bash run-local.sh` after changing `.env.local`. The search worker will count every configured source in `sources_checked`, deduplicate canonical URLs, refresh `last_seen`, and score each role against the saved profile.

## LinkedIn boundary

LinkedIn publishes API documentation, but job-related access is restricted to approved integrations/partners. LinkedIn also prohibits unauthorized crawlers, bots, browser plug-ins, and automated activity. A future LinkedIn connector must use a LinkedIn-approved application, OAuth credentials supplied by the user, and the permitted data scope. Until that exists, Neural Ant only links users to official postings and keeps application submission under the user's control.

## Official references

- [LinkedIn API overview](https://learn.microsoft.com/en-us/linkedin)
- [LinkedIn prohibited software and extensions](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software)
- [LinkedIn Job Posting API access note](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2025-10)
- [SmartRecruiters Posting API](https://developers.smartrecruiters.com/docs/posting-api)
- [Adzuna API overview](https://developer.adzuna.com/overview)
- [USAJOBS Job APIs](https://developer.usajobs.gov/api-reference/job-apis)
