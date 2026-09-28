#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_CREATOR="/Users/noahhorton/.codex/skills/.system/plugin-creator"
PLUGIN_HOME="$HOME/plugins/task-matrix"
MARKETPLACE_FILE="$HOME/.agents/plugins/marketplace.json"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST="$AGENTS_DIR/net.noahhorton.task-matrix.plist"
LABEL="net.noahhorton.task-matrix"
UID_VALUE="$(id -u)"
DATA_FILE="$PROJECT_DIR/data/tasks.json"

if [[ ! -f "$PLUGIN_CREATOR/scripts/create_basic_plugin.py" ]]; then
  echo "Codex plugin-creator helper was not found: $PLUGIN_CREATOR" >&2
  exit 1
fi

if [[ ! -f "$MARKETPLACE_FILE" ]]; then
  python3 "$PLUGIN_CREATOR/scripts/create_basic_plugin.py" task-matrix --path "$HOME/plugins" --with-mcp --with-marketplace
else
  MARKETPLACE_NAME="$(python3 "$PLUGIN_CREATOR/scripts/read_marketplace_name.py")"
  if ! python3 - "$MARKETPLACE_FILE" <<'PY'
import json, sys
from pathlib import Path
market = json.loads(Path(sys.argv[1]).read_text())
raise SystemExit(0 if any(p.get("name") == "task-matrix" for p in market.get("plugins", []) if isinstance(p, dict)) else 1)
PY
  then
    python3 "$PLUGIN_CREATOR/scripts/create_basic_plugin.py" task-matrix --path "$HOME/plugins" --with-mcp --with-marketplace --marketplace-name "$MARKETPLACE_NAME"
  fi
  [[ -d "$PLUGIN_HOME" ]] || mkdir -p "$PLUGIN_HOME"
fi
mkdir -p "$PLUGIN_HOME"
cp -R "$PROJECT_DIR/plugin/." "$PLUGIN_HOME/"
python3 - "$PLUGIN_HOME/.mcp.json" "$PLUGIN_HOME/server.py" "$DATA_FILE" <<'PY'
import json, sys
from pathlib import Path

manifest = Path(sys.argv[1])
config = json.loads(manifest.read_text())
server = config["mcpServers"]["task-matrix"]
server["args"][0] = sys.argv[2]
server["env"]["TASK_MATRIX_DATA"] = sys.argv[3]
manifest.write_text(json.dumps(config, indent=2) + "\n")
PY
mkdir -p "$PROJECT_DIR/data"
python3 "$PLUGIN_CREATOR/scripts/update_plugin_cachebuster.py" "$PLUGIN_HOME"
MARKETPLACE_NAME="$(python3 "$PLUGIN_CREATOR/scripts/read_marketplace_name.py")"
codex plugin add "task-matrix@$MARKETPLACE_NAME"

mkdir -p "$AGENTS_DIR"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/python3</string><string>$PLUGIN_HOME/server.py</string><string>web</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/Task Matrix/server.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/Task Matrix/server-error.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TASK_MATRIX_DATA</key><string>$DATA_FILE</string>
    <key>TASK_MATRIX_PORT</key><string>8765</string>
  </dict>
</dict>
</plist>
PLIST_EOF
mkdir -p "$HOME/Library/Logs/Task Matrix"
launchctl bootout "gui/$UID_VALUE" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_VALUE" "$PLIST"
launchctl kickstart -k "gui/$UID_VALUE/$LABEL"
for attempt in {1..20}; do
  if /usr/bin/curl --fail --silent http://127.0.0.1:8765/health >/dev/null; then break; fi
  sleep 0.25
done
/usr/bin/curl --fail --silent http://127.0.0.1:8765/health
printf '\nInstalled Task Matrix. Open with: %s/open-task-matrix.sh\n' "$PLUGIN_HOME"
