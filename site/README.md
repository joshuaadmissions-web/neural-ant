# Neural Ant static preview

This folder is a public, static product preview inspired by the structure of modern agent workflow sites. It uses original Neural Ant copy and styling and contains no profile or resume data.

## Free hosting with Cloudflare Pages

1. Sign in to Cloudflare and choose **Workers & Pages → Create → Pages → Connect to Git**.
2. Select the public `joshuaadmissions-web/neural-ant` repository and the `main` branch.
3. Set the root directory to `site`. Use no build command; set the output directory to `.` (the folder itself).
4. Save and deploy. Cloudflare Pages will create a public `pages.dev` address and redeploy when changes are pushed to `main`.

The exact dashboard labels may change. Cloudflare Free currently documents 500 Pages builds/month and up to 20,000 files per site, with a 25 MiB per-file limit. Check the provider's current plan terms before relying on those quotas.

## Important boundary

This only hosts the static preview. It does not host Neural Ant's FastAPI backend, database, resume storage, or the job-search worker. Do not put a resume, profile export, API key, or private settings into this folder. The full app currently runs locally using `bash run-local.sh`; hosting the authenticated full application needs a separate backend and persistent private storage.
