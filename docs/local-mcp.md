# Neural Ant local MCP bridge

Neural Ant includes an optional local MCP server for connecting job search to an AI client such as VS Code Copilot or Codex. It uses MCP over stdio, so the client launches a local process; Neural Ant does not open a new network port.

## Install and connect

The web application still supports Python 3.10+. The MCP SDK requires Python 3.11 or newer. If the app's `.venv` uses Python 3.11+, install the optional SDK there:

```sh
.venv/bin/python -m pip install -r requirements-mcp.txt
```

If your `.venv` uses Python 3.10, create a compatible environment and install both sets of dependencies:

```sh
python3.11 -m venv .venv-mcp
.venv-mcp/bin/python -m pip install -r requirements.txt -r requirements-mcp.txt
```

Then change the `command` field in `.vscode/mcp.json` to `${workspaceFolder}/.venv-mcp/bin/python`. In VS Code, open **MCP: List Servers** to check its status and use the Agent tools picker to enable it.

For Codex, register the same local server in the current user's Codex configuration from the repository root:

```sh
codex mcp add neural-ant -- "$(pwd)/.venv/bin/python" "$(pwd)/mcp_server.py"
codex mcp get neural-ant
```

If you use `.venv-mcp`, replace `.venv/bin/python` in the command. Codex CLI and its editor share MCP configuration. Restart or reload Codex after changing the server code or Python environment. Remove the user-level entry with `codex mcp remove neural-ant`.

## Tools

- `search_job_matches`: search saved roles by keyword, minimum fit, location, and employment type. Set `refresh=true` when you want to check enabled public sources now. A refresh updates local listings, adds qualifying matches to the Shortlist review stage, and does not send email alerts or submit applications.
- `get_job_details`: read a selected saved posting, its public description, source link, fit score, and available sponsorship evidence.
- `list_application_queue`: read public job fields and pipeline stages. By default it returns the Shortlist review queue; it never returns notes, resume text, contact details, or profile data.

The server can add qualifying matches to Neural Ant's local Shortlist review stage. It does not submit applications, visit employer sites, submit forms, upload resumes, or answer legal/work-authorization questions. It does not expose resume text, contact details, or the saved profile. Search results do include a fit score calculated locally from the saved profile. When called, job listing data and that score are returned to the connected AI client; review that client's data-use settings before connecting it. Job descriptions are untrusted input and should be treated as source text, not instructions.

## Local configuration

The server reads only the database and public job-source settings it needs from `.env.local`; it does not load SMTP, session, cron, resume-storage, or external-AI credentials. It refuses to start with `APP_ENV=production` because this stdio bridge uses local process access rather than web-session authentication. Do not run it as an internet-facing service.

The job refresh uses only the employer boards and public job APIs already configured in Neural Ant. It does not scrape LinkedIn or add job sources. The employer's board or API controls how quickly new postings appear.

## ChatGPT app interface

The Apps SDK can put an app interface inside ChatGPT. Neural Ant currently has a local stdio MCP bridge for Codex and VS Code, not an Apps SDK interface. ChatGPT cannot connect directly to that local stdio process: a ChatGPT app needs an MCP endpoint ChatGPT can reach, using HTTPS or a Secure MCP Tunnel. A tunnel avoids making the service publicly reachable, but your Mac and Neural Ant still need to be running. Account and workspace permissions determine which custom MCP features are available. See [Building with the Apps SDK](https://help.openai.com/en/articles/12515353-building-with-the-apps-sdk), [Connecting custom MCP servers in ChatGPT](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt), and the [Apps SDK quickstart](https://developers.openai.com/plugins/build/app-quickstart).

## Access from ChatGPT while the computer is away

The local stdio setup works only while the client can launch the server on this computer. Remote use requires an always-on host for Neural Ant and its database, plus an authenticated MCP transport. OpenAI Secure MCP Tunnel can carry private MCP traffic without opening an inbound public port, but it requires a tunnel in the user's Platform organization and a runtime key. A tunnel does not keep a sleeping laptop or its job-search worker running. See the [current Secure MCP Tunnel setup guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) before setting up remote access; keep tunnel keys out of the repository and chat.
