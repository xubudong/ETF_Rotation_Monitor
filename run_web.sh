#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

load_dotenv() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#${line%%[![:space:]]*}}"
    line="${line%${line##*[![:space:]]}}"
    [[ -z "$line" || "${line:0:1}" == "#" || "$line" != *=* ]] && continue
    local name="${line%%=*}"
    local value="${line#*=}"
    name="${name//[[:space:]]/}"
    [[ -z "$name" ]] && continue
    if [[ -z "${!name-}" ]]; then
      value="${value%\"}"
      value="${value#\"}"
      value="${value%\'}"
      value="${value#\'}"
      export "$name=$value"
    fi
  done < "$file"
}

load_dotenv "$ROOT_DIR/.env"

FOREGROUND=0
if [[ "${1-}" == "--foreground" ]]; then
  FOREGROUND=1
fi

HOST_ADDRESS="${WEB_HOST:-127.0.0.1}"
START_PORT=${WEB_PORT:-8020}
PORT_SCAN_LIMIT="${WEB_PORT_SCAN_LIMIT:-30}"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_FILE="$RUNTIME_DIR/web.pid"
mkdir -p "$LOG_DIR"

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

PORT="$($PYTHON -c "import socket, sys; host=sys.argv[1]; start=int(sys.argv[2]); limit=int(sys.argv[3]); bind_host='' if host == '0.0.0.0' else host; found=None
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

URL="http://${HOST_ADDRESS}:${PORT}"
if [[ "$FOREGROUND" == "1" ]]; then
  echo "Starting ETF market rotation monitor in foreground at ${URL}"
  exec "$PYTHON" -m uvicorn web_app.server:app --host "$HOST_ADDRESS" --port "$PORT"
fi

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "ETF market rotation monitor is already running: PID ${OLD_PID}, ${URL}"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
STDOUT_LOG="$LOG_DIR/web_${TIMESTAMP}.out.log"
STDERR_LOG="$LOG_DIR/web_${TIMESTAMP}.err.log"
nohup "$PYTHON" -m uvicorn web_app.server:app --host "$HOST_ADDRESS" --port "$PORT" >"$STDOUT_LOG" 2>"$STDERR_LOG" &
PID="$!"
echo "$PID" > "$PID_FILE"

echo "ETF market rotation monitor started."
echo "URL: ${URL}"
echo "PID: ${PID}"
echo "PID file: ${PID_FILE}"
echo "Logs: ${STDOUT_LOG} ; ${STDERR_LOG}"
echo "Stop: ./stop_web.sh"
