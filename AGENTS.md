# Task Matrix project instructions

The editable plugin source lives in `plugin/`. The locally installed copy is `~/plugins/task-matrix`, and the board service runs as the `net.noahhorton.task-matrix` LaunchAgent on `http://127.0.0.1:8765/`.

After making any edits in this repository, run `./install-local.sh` from the repository root. It copies the plugin source and assets into the installed plugin, refreshes the plugin cache, and restarts the board service. Confirm the service is healthy at `http://127.0.0.1:8765/health` before finishing.

Make changes in this repository, not directly in `~/plugins/task-matrix`; the install script is the supported way to refresh the local app.
