#!/usr/bin/env bash
set -euo pipefail

scriptDir=$(cd "$(dirname "$0")" && pwd)
cd "$scriptDir"

pythonBin="python"
if [ -x ".venv/bin/python" ]; then
    pythonBin=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
    pythonBin=".venv/Scripts/python.exe"
fi

export PORT="${PORT:-7681}"

exec "$pythonBin" sessionBroker.py
