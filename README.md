# Task Matrix

Noah's local task matrix for Codex desktop. The installable plugin and board live in [plugin/](plugin/).

## Install from source

On macOS, install Task Matrix from this repository with the Codex CLI and Python 3 available:

```sh
git clone https://github.com/noah-horton/task-matrix.git
cd task-matrix
./install-local.sh
```

The installer copies the plugin into `~/plugins/task-matrix`, registers it in your personal Codex marketplace, installs it with `codex plugin add`, and starts the board service as a per-user LaunchAgent. It writes the MCP server and data file paths for your checkout, so you can clone the repository into any directory. The installer also uses the plugin-creator helper bundled with Codex at `~/.codex/skills/.system/plugin-creator`.

After installation, start a new Codex chat to load the tools. Open the board in Codex's in-app browser at `http://127.0.0.1:8765/` and keep it open while working with tasks. The installer starts the server automatically at login; if needed, start it with `python3 ~/plugins/task-matrix/server.py web`.

Task data stays in the checkout's `data/tasks.json`, which Git ignores. A fresh clone therefore starts with an empty task list. Export the board to JSON before moving tasks between installations.

For any task activity in Codex, first ensure the Task Matrix web server process is running (`http://127.0.0.1:8765/health`); if it is down, start it with `python3 ~/plugins/task-matrix/server.py web`. Then open `http://127.0.0.1:8765/` in Codex's in-app browser and keep the board open while working with tasks. The plugin instructions and tool descriptions specify this workflow.

The task file is data/tasks.json in this project. It is shared by the browser board and Codex MCP tools and ignored by Git. The service binds only to 127.0.0.1.

`open-task-matrix.sh` opens the board in the default external browser.

The synced Obsidian prototype was copied for this package and left unchanged. If it contains browser-local tasks, export them from that original board and import the JSON backup into the installed board.
