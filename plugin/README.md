# Task Matrix

The board and Codex tools share one task file at:

the project’s data/tasks.json

The board uses http://127.0.0.1:8765. It only listens on this Mac's loopback interface. Data is written atomically and locked across the web app and MCP server so both can update it safely.

For any activity involving tasks, ensure the web server process is running first (check http://127.0.0.1:8765/health; if it is down, start it with `python3 ~/plugins/task-matrix/server.py web`). Then open http://127.0.0.1:8765/ in Codex's captive browser and keep the board open while working with tasks. The plugin's default prompt and MCP tool descriptions provide this instruction.

## Board

Use Codex's in-app browser to open http://127.0.0.1:8765/. The board has the 3×3 importance/urgency matrix, task links and descriptions, due dates, Doing/Tracking filters, completion, drag-and-drop, and JSON import/export. It refreshes task changes made by Codex. The `open-task-matrix.sh` helper opens the board in the system's default browser.

Classify a task by starting its name with a single word and a colon, such as `Brett: Follow up`. Prefix words can contain letters, numbers, and underscores; spaces and punctuation before the colon are not part of a prefix. The Prefix dropdown starts with All, followed by the distinct prefixes in title case, sorted alphabetically. For example, `BRETT:` and `brett:` both appear as Brett. The list includes open and completed tasks and updates after additions, renames, deletions, imports, and changes from Codex. If the selected prefix disappears, the filter returns to All. Prefix and Doing/Tracking filters combine and apply to the matrix, summary counts, and completed tasks. Task names retain their original spelling.

## Create a macOS Dock entry

Install Task Matrix first using `./install-local.sh` from the repository root. The installer starts the board service at login. This launcher opens the board in your default browser; the service must be running at <http://127.0.0.1:8765/health>.

### Create the launcher

1. Open **Script Editor** (in Applications → Utilities) and create a new AppleScript document.
2. Paste this script:

   ```applescript
   open location "http://127.0.0.1:8765/"
   ```

3. Choose **File → Export**, set **File Format** to **Application**, and name it **Task Matrix.app**. Leave **Stay open after run handler** unchecked.
4. Save it in your home folder's **Applications** folder (`~/Applications`; create the folder if needed). Double-click it to confirm that it opens the board.

### Apply the shield icon and pin it

1. In Finder, choose **Go → Go to Folder** (Shift-Command-G) and enter `~/plugins/task-matrix/assets/`.
2. Open **task-matrix-icon.png** in **Preview**. Choose **Edit → Select All**, then **Edit → Copy** to copy the image itself.
3. Select **Task Matrix.app** in Finder and choose **File → Get Info** (Command-I).
4. Click the **small icon in the upper-left corner** of the Info window, then press **Command-V**. Close the Info window.
5. Drag **Task Matrix.app** from Finder into the applications section of the Dock (to the left of the separator on a horizontal Dock). Click the shield to open Task Matrix.

If the Dock still displays the old icon, drag that Dock entry out to remove it, then drag the application back in. Keep the `.app` in `~/Applications`; the Dock entry points to it. The launcher exits after opening the browser, so its running indicator only appears briefly.

The [1024×1024 PNG](assets/task-matrix-icon.png) has a transparent background and contains only the original logo's shield and decorative strokes, centered with padding. The [square SVG](assets/task-matrix-icon.svg) preserves the original vector paths and gold gradient. A [multi-resolution macOS `.icns` file](assets/task-matrix-icon.icns) is also supplied for application bundles; use the PNG for the Preview copy-and-paste steps above. Installation copies all three files into `~/plugins/task-matrix/assets/`.

Apple documents [saving a script as an application](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/SaveaScript.html), [changing a file's icon](https://support.apple.com/guide/mac-help/mchlp2313/mac), and [adding applications to the Dock](https://support.apple.com/guide/mac-help/mh35859/mac).

## Codex tools

The local plugin supplies list_tasks, create_task, update_task, complete_task, and delete_task. Install it from the personal marketplace. Start a new Codex chat after installation so its tools load.

`list_tasks` accepts `name_regex`, a Python regular expression searched against task names, ignoring case by default. Use `{"name_regex": "^Brett:"}` for open Brett tasks or `{"status": "all", "name_regex": "^(?:Brett|Alice):"}` to include completed tasks for either prefix. Regex search combines with all other filters; malformed expressions return a tool error. Add or change a classification through the existing `name` field in `create_task` or `update_task`.

## Data and backup

Use Export in the board for a portable JSON backup. Import merges by task id. The original Obsidian prototype remains unchanged; browser localStorage from that file URL is separate from this new shared data file.

## Updating

From the project source, rerun ./install-local.sh. This copies the plugin, refreshes its Codex cachebuster, and reinstalls the local marketplace entry. The LaunchAgent starts the board service at login. To open the board, run ~/plugins/task-matrix/open-task-matrix.sh.
