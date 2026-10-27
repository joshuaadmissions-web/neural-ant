#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.10 or newer, then run this again."
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required to build the app. Install Node.js 20 or newer, then run this again."
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm run build

if [ ! -f .env.local ]; then
  cp .env.local.example .env.local
  session_secret="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cron_secret="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
  python - "$session_secret" "$cron_secret" <<'PYINIT'
from pathlib import Path
import sys

path = Path(".env.local")
text = path.read_text()
text = text.replace("SESSION_SECRET=generated-by-run-local-script", f"SESSION_SECRET={sys.argv[1]}")
text = text.replace("CRON_SECRET=generated-by-run-local-script", f"CRON_SECRET={sys.argv[2]}")
path.write_text(text)
PYINIT
  chmod 600 .env.local
fi

echo "Neural Ant is starting at http://127.0.0.1:8080"
echo "Keep this Terminal window open while using the app. Press Ctrl+C to stop it."
exec python -m uvicorn api.main:app --env-file .env.local --host 127.0.0.1 --port 8080
