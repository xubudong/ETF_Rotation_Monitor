#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT_DIR/runtime/web.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found. ETF market rotation monitor does not appear to be running."
  exit 0
fi

PID="$(cat "$PID_FILE" || true)"
if [[ -z "$PID" ]]; then
  rm -f "$PID_FILE"
  echo "PID file was empty and has been removed."
  exit 0
fi

if ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "Process ${PID} is not running. PID file removed."
  exit 0
fi

kill "$PID"
rm -f "$PID_FILE"
echo "Stopped ETF market rotation monitor, PID ${PID}."
