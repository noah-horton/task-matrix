#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_HOME="$HOME/plugins/task-matrix"
MARKETPLACE_FILE="$HOME/.agents/plugins/marketplace.json"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST="$AGENTS_DIR/net.noahhorton.task-matrix.plist"
LABEL="net.noahhorton.task-matrix"
UID_VALUE="$(id -u)"
DATA_FILE="$PROJECT_DIR/data/tasks.json"

python3 - "$MARKETPLACE_FILE" "$PLUGIN_HOME" <<'PYTHON'
import json, sys
from pathlib import Path
marketplace = Path(sys.argv[1])
marketplace.parent.mkdir(parents=True, exist_ok=True)
market = json.loads(marketplace.read_text()) if marketplace.exists() else {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
if not any(p.get("name") == "task-matrix" for p in market.get("plugins", []) if isinstance(p, dict)):
    market.setdefault("plugins", []).append({"name": "task-matrix", "source": {"source": "local", "path": sys.argv[2]}, "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"})
    marketplace.write_text(json.dumps(market, indent=2) + "\n")
PYTHON
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
python3 - "$PLUGIN_HOME/.codex-plugin/plugin.json" <<'PYTHON'
import datetime, json, sys
from pathlib import Path
manifest = Path(sys.argv[1])
plugin = json.loads(manifest.read_text())
plugin["version"] = plugin["version"].split("+")[0] + "+codex." + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S%f")
manifest.write_text(json.dumps(plugin, indent=2) + "\n")
PYTHON
MARKETPLACE_NAME="$(python3 - "$MARKETPLACE_FILE" <<'PYTHON'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["name"])
PYTHON
)"
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
