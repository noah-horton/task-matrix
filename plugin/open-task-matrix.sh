#!/bin/bash
set -euo pipefail
URL="http://127.0.0.1:8765/"
if ! /usr/bin/curl --fail --silent "$URL" >/dev/null; then
  echo "Task Matrix local service is not running. Run the project install-local.sh again." >&2
  exit 1
fi
/usr/bin/open "$URL"
