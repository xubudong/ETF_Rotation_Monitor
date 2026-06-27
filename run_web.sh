#!/usr/bin/env bash
set -euo pipefail

HOST_ADDRESS="${WEB_HOST:-127.0.0.1}"
START_PORT="${WEB_PORT:-8000}"
PORT_SCAN_LIMIT="${WEB_PORT_SCAN_LIMIT:-30}"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "Python was not found. Install Python 3.10+ or create .venv first." >&2
  exit 1
fi

PORT="$("$PYTHON" -c "import socket, sys; host=sys.argv[1]; start=int(sys.argv[2]); limit=int(sys.argv[3]); bind_host='' if host == '0.0.0.0' else host; found=None
for port in range(start, start + limit):
    s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((bind_host, port))
        found=port
        break
    except OSError:
        pass
    finally:
        s.close()
if found is None:
    raise SystemExit(1)
print(found)" "$HOST_ADDRESS" "$START_PORT" "$PORT_SCAN_LIMIT")" || {
  end_port=$((START_PORT + PORT_SCAN_LIMIT - 1))
  echo "No available TCP port found from ${START_PORT} to ${end_port}. Set WEB_PORT to another port and retry." >&2
  exit 1
}

if [[ "$PORT" != "$START_PORT" ]]; then
  echo "Port ${START_PORT} is unavailable; using ${PORT} instead."
fi

echo "Starting ETF market rotation monitor at http://${HOST_ADDRESS}:${PORT}"
"${PYTHON}" -m uvicorn web_app.server:app --host "${HOST_ADDRESS}" --port "${PORT}"
