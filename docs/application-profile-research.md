# Application profile and resume tailoring research

## Scope

The application workflow was designed around reusable candidate-profile fields, not around one fixed employer form. Employer portals reuse a core profile but add job-specific questions, consent notices, screening questions, attachments, and employer-specific account steps. A single “fill everything” map would therefore be incomplete and unsafe.

Official portal documentation shows the recurring profile categories:

- Greenhouse MyGreenhouse: contact details, resume, employment, education, online profiles, worksite preferences, languages, and location; candidates can edit autofilled answers before submitting.
- Lever: resume, full name, email, phone, current location, current company, links, and configurable text, dropdown, file-upload, multiple-choice, checkbox, and university questions.
- Workday: contact and personal information, address, job history, education, skills, certifications/licenses, languages, and external links; employer-specific questions are not part of the reusable profile.
- iCIMS: resume parsing can populate profile fields, followed by profile editing, screening questions, EEO questions, and job-specific questions.
- SAP SuccessFactors: candidate-profile background elements support multiple work, education, and language entries, while application forms add job- and region-specific fields.
- SmartRecruiters, Taleo, and Jobvite similarly support attachments, custom screening questions, consent/privacy choices, and job-specific application flows.

The implementation consequently has three layers:

1. Reusable fields that the user edits once in Neural Ant.
2. Label-matched, empty-field autofill for common non-sensitive fields in the local Chrome extension.
3. A review stop for credentials, privacy consent, work authorization, sponsorship, demographic/EEO, background, signature, and job-specific questions.

No employer account passwords or credentials are stored in Neural Ant.

## Reusable profile schema

The editable application profile covers:

- preferred name, contact details, address, city/state/postal code/country;
- LinkedIn, GitHub, portfolio, and other website links;
- employment-history entries with employer, title, dates, location, and verified highlights;
- education entries with school, degree, field, and dates;
- certifications/licenses, languages and proficiency;
- availability date, notice period, employment-type preferences, relocation, and travel preference;
- the existing resume, skills, target roles, salary, work-mode, and location preferences.

Dates, employers, titles, skills, and achievements must come from the user's verified source material. Tailoring may reorder or clarify verified evidence, but it must not invent qualifications or add keywords solely to manipulate a screening system.

## Resume and application preparation principles

- Use standard section headings, readable text, normal work-history formatting, and parsable layouts. Avoid tables, text boxes, headers/footers that contain essential data, photos, and decorative graphics when a portal parser is expected.
- Map the job description to a transparent evidence matrix: requirement, matching resume evidence, gap/unknown, and the exact resume line used.
- Prefer specific action plus result plus scope/metric when the user has a verified metric. Never manufacture a metric.
- Keep a role-specific resume variant and a local draft history so the user can see what changed.
- The application tracker can download a plain, ATS-friendly DOCX named `Company_Role_Name_Resume.docx`. It uses standard headings, readable typography, and simple paragraphs/bullets; the user must review the facts and wording before upload.
- Treat fit scores and LLM output as review aids, not hiring predictions or guarantees.
- Do not optimize for demographic or other protected characteristics. Research shows that hiring systems can reproduce bias; the product should preserve truthful evidence and let the candidate control optional disclosures.

## Portal coverage strategy

Neural Ant currently discovers public jobs from Greenhouse, Lever, and Ashby. The extension is deliberately portal-agnostic: it inspects visible HTTPS pages and labels rather than attempting to log in to dozens of vendor-specific accounts. This covers the shared field vocabulary across major ATS families while avoiding brittle selectors and unsupported account automation.

Future portal validation should be a test matrix, not a promise that every employer portal has identical behavior. Each portal family needs a controlled fixture and a manual check for account creation, resume parsing, repeated profile fields, custom questions, file uploads, privacy consent, and “save for later” behavior before any new field is enabled.

## Sources

- [Greenhouse MyGreenhouse FAQ for candidates](https://support.greenhouse.io/hc/en-us/articles/43418495049499-MyGreenhouse-FAQ-for-Candidates)
- [Greenhouse MyGreenhouse Quick Apply](https://support.greenhouse.io/hc/en-us/articles/35746094035099-MyGreenhouse-Quick-Apply)
- [Lever application form configuration](https://help.lever.co/s/article/Configuring-your-Lever-Application-Form)
- [Workday candidate profile](https://community-content.workday.com/en-us/public/products/talent-management/talent-acquisition/workday-candidate-profile.html)
- [SmartRecruiters post-an-application API](https://developers.smartrecruiters.com/docs/post-an-application)
- [SAP SuccessFactors candidate profile](https://help.sap.com/docs/successfactors-recruiting/setting-up-and-maintaining-sap-successfactors-recruiting/candidate-profile-in-sap-successfactors)
- [iCIMS candidate guide](https://community.icims.com/articles/Knowledge/Candidate-Guide-to-the-iCIMS-Talent-Platform)
- [Oracle Taleo application flow](https://chicago.taleo.net/careersection/2026PRD.1.2.7.3.0/help/Output/careersection/careersectiondoc/applicationflow/c_applicationflow.html)
- [Jobvite pre-screening forms](https://help.jobvite.com/articles/Knowledge/Pre-screening-Forms)
- [Harvard FAS resume and cover-letter guidance](https://careerservices.fas.harvard.edu/resources/resumes-cover-letters-for-phd-students/)
- [UC Berkeley resume guidance](https://www.career.berkeley.edu/prepare-for-success/resumes/)
- [Nature Human Behaviour field experiment on making experience salient](https://www.nature.com/articles/s41562-022-01485-6)
