#!/usr/bin/env python3
"""Task Matrix local HTTP board and stdio MCP server (Python standard library only)."""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
import re
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
DATA_FILE = Path(os.environ.get("TASK_MATRIX_DATA", Path.home() / "Library/Application Support/Task Matrix/tasks.json"))
LOCK_FILE = DATA_FILE.with_suffix(".lock")
LEVELS = {"high", "medium", "low"}


def valid_task(task):
    if not isinstance(task, dict):
        raise ValueError("Each task must be an object.")
    if not isinstance(task.get("id"), str) or not task["id"].strip() or len(task["id"]) > 160:
        raise ValueError("Task id is required.")
    if not isinstance(task.get("name"), str) or not task["name"].strip() or len(task["name"]) > 160:
        raise ValueError("Task name is required and must be at most 160 characters.")
    if task.get("importance") not in LEVELS or task.get("urgency") not in LEVELS:
        raise ValueError("Importance and urgency must be high, medium, or low.")
    due = task.get("dueDate", "")
    if due:
        try:
            dt.date.fromisoformat(due)
        except (TypeError, ValueError):
            raise ValueError("Due date must be a real date in YYYY-MM-DD format.")
    url = task.get("url", "")
    if url:
        if not isinstance(url, str):
            raise ValueError("External links must be valid http:// or https:// URLs.")
        parsed_url = urlparse(url)
        if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.hostname:
            raise ValueError("External links must be valid http:// or https:// URLs.")
    clean = {
        "id": task["id"].strip(), "name": task["name"].strip(),
        "description": str(task.get("description") or "")[:1600],
        "url": url or "", "dueDate": due or "",
        "importance": task["importance"], "urgency": task["urgency"],
        "doing": task.get("doing") is not False,
        "today": task.get("today") is True,
        "completed": task.get("completed") is True,
        "createdAt": task.get("createdAt") or dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    order = task.get("matrixOrder")
    if order is not None:
        if type(order) is not int or not 0 <= order <= 9007199254740991:
            raise ValueError("Matrix order must be a non-negative safe integer.")
        clean["matrixOrder"] = order
    return clean


def read_tasks():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        try:
            if not DATA_FILE.exists():
                return []
            payload = json.loads(DATA_FILE.read_text())
            return [valid_task(t) for t in payload.get("tasks", [])]
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def change_tasks(upserts=(), deletes=()):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if DATA_FILE.exists():
                payload = json.loads(DATA_FILE.read_text())
                current = {t["id"]: valid_task(t) for t in payload.get("tasks", [])}
            else:
                current = {}
            for task_id in deletes:
                current.pop(str(task_id), None)
            for task in upserts:
                clean = valid_task(task)
                current[clean["id"]] = clean
            result = sorted(current.values(), key=lambda t: (t["createdAt"], t["id"]))
            fd, temp_name = tempfile.mkstemp(prefix="tasks.", suffix=".json", dir=DATA_FILE.parent)
            try:
                with os.fdopen(fd, "w") as tmp:
                    json.dump({"version": 1, "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "tasks": result}, tmp, indent=2)
                    tmp.write("\n")
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(temp_name, DATA_FILE)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            return result
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/tasks":
            return self.send_json(200, {"tasks": read_tasks()})
        if path == "/health":
            return self.send_json(200, {"ok": True, "dataFile": str(DATA_FILE)})
        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
            "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
            "/offline.html": ("offline.html", "text/html; charset=utf-8"),
        }
        for name in ("task-matrix-icon.svg", "favicon-32.png", "apple-touch-icon.png", "pwa-icon-192.png", "pwa-icon-512.png"):
            static_files[f"/assets/{name}"] = (f"assets/{name}", "image/svg+xml" if name.endswith(".svg") else "image/png")
        if path in static_files:
            filename, content_type = static_files[path]
            body = (ROOT / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return self.wfile.write(body)
        return self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/tasks":
            return self.send_json(404, {"error": "Not found"})
        origin = self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:8765", "http://localhost:8765"):
            return self.send_json(403, {"error": "Cross-origin requests are not allowed."})
        try:
            body = self.read_body()
            tasks = change_tasks(body.get("upsert", []), body.get("deleteIds", []))
            return self.send_json(200, {"tasks": tasks})
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})

    def read_body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > 2_000_000:
            raise ValueError("Request is too large.")
        return json.loads(self.rfile.read(size) or b"{}")


TOOLS = [
    {"name": "list_tasks", "description": "Before any task-related activity, ensure the Task Matrix web server is running and open http://127.0.0.1:8765/ in Codex's captive browser. Then list tasks, optionally filtered by open/completed status, Doing/Tracking, importance, urgency, due date, or a case-insensitive regular expression on the task name. A leading single word followed by a colon classifies a task; use name_regex '^Brett:' to find Brett tasks. Filters combine; status defaults to open, so use status all to include completed tasks.", "inputSchema": {"type": "object", "properties": {"today": {"type": "boolean", "description": "Filter by the persistent Today tag."}, "status": {"type": "string", "enum": ["open", "completed", "all"]}, "work_type": {"type": "string", "enum": ["doing", "tracking", "all"]}, "importance": {"type": "string", "enum": ["high", "medium", "low"]}, "urgency": {"type": "string", "enum": ["high", "medium", "low"]}, "due_before": {"type": "string", "description": "Inclusive YYYY-MM-DD cutoff."}, "name_regex": {"type": "string", "description": "Python regular expression searched against task names, case-insensitive by default. Example: ^Brett: matches the Brett prefix; ^(?:Brett|Alice): matches either prefix. Invalid expressions return a tool error."}}, "additionalProperties": False}},
    {"name": "create_task", "description": "Before any task-related activity, ensure the Task Matrix web server is running and open http://127.0.0.1:8765/ in Codex's captive browser. Then create a task in Noah's local Task Matrix.", "inputSchema": {"type": "object", "required": ["name", "importance", "urgency"], "properties": {"today": {"type": "boolean", "description": "Include in Today without changing matrix placement."}, "name": {"type": "string"}, "description": {"type": "string"}, "url": {"type": "string"}, "due_date": {"type": "string", "description": "YYYY-MM-DD"}, "importance": {"type": "string", "enum": ["high", "medium", "low"]}, "urgency": {"type": "string", "enum": ["high", "medium", "low"]}, "work_type": {"type": "string", "enum": ["doing", "tracking"], "default": "doing"}}, "additionalProperties": False}},
    {"name": "update_task", "description": "Before any task-related activity, ensure the Task Matrix web server is running and open http://127.0.0.1:8765/ in Codex's captive browser. Then update task fields by id. Provide only fields to change; completed can reopen a task.", "inputSchema": {"type": "object", "required": ["id"], "properties": {"today": {"type": "boolean", "description": "Add or remove the Today tag."}, "id": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}, "url": {"type": "string"}, "due_date": {"type": "string"}, "importance": {"type": "string", "enum": ["high", "medium", "low"]}, "urgency": {"type": "string", "enum": ["high", "medium", "low"]}, "work_type": {"type": "string", "enum": ["doing", "tracking"]}, "completed": {"type": "boolean"}}, "additionalProperties": False}},
    {"name": "complete_task", "description": "Before any task-related activity, ensure the Task Matrix web server is running and open http://127.0.0.1:8765/ in Codex's captive browser. Then mark a task complete, or reopen it when completed is false.", "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "completed": {"type": "boolean", "default": True}}, "additionalProperties": False}},
    {"name": "delete_task", "description": "Before any task-related activity, ensure the Task Matrix web server is running and open http://127.0.0.1:8765/ in Codex's captive browser. Then delete a task by id from the local Task Matrix.", "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}, "additionalProperties": False}},
]


def call_tool(name, a):
    tasks = read_tasks()
    if name == "list_tasks":
        pattern = None
        if "name_regex" in a:
            if not isinstance(a["name_regex"], str):
                raise ValueError("name_regex must be a string.")
            try:
                pattern = re.compile(a["name_regex"], re.IGNORECASE)
            except re.error as exc:
                raise ValueError(f"Invalid name_regex: {exc}") from exc
        result = tasks
        if a.get("status", "open") != "all":
            result = [t for t in result if t["completed"] == (a.get("status") == "completed")]
        if a.get("work_type", "all") != "all":
            result = [t for t in result if t["doing"] == (a["work_type"] == "doing")]
        if "today" in a:
            result = [t for t in result if t["today"] == a["today"]]
        for key in ("importance", "urgency"):
            if a.get(key):
                result = [t for t in result if t[key] == a[key]]
        if a.get("due_before"):
            result = [t for t in result if t["dueDate"] and t["dueDate"] <= a["due_before"]]
        if pattern is not None:
            result = [t for t in result if pattern.search(t["name"])]
        return result
    if name == "create_task":
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        task = valid_task({"id": __import__("uuid").uuid4().hex, "name": a.get("name"), "description": a.get("description"), "url": a.get("url"), "dueDate": a.get("due_date"), "importance": a.get("importance"), "urgency": a.get("urgency"), "doing": a.get("work_type", "doing") == "doing", "completed": False, "today": a.get("today", False), "createdAt": now})
        change_tasks([task])
        return task
    if name in ("update_task", "complete_task", "delete_task"):
        task_id = a.get("id")
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            raise ValueError("No task exists with that id.")
        if name == "delete_task":
            change_tasks(deletes=[task_id])
            return {"deleted": True, "id": task_id}
        update = {}
        if name == "complete_task":
            update["completed"] = a.get("completed", True)
        else:
            keys = {"name", "description", "url", "importance", "urgency", "completed", "today"}
            update.update({k: v for k, v in a.items() if k in keys})
            if "due_date" in a:
                update["dueDate"] = a["due_date"]
            if "work_type" in a:
                update["doing"] = a["work_type"] == "doing"
        merged = valid_task({**task, **update})
        if any(merged[key] != task[key] for key in ("importance", "urgency")):
            merged.pop("matrixOrder", None)
        change_tasks([merged])
        return merged
    raise ValueError("Unknown task tool.")


def mcp_loop():
    def respond(message):
        method = message.get("method")
        ident = message.get("id")
        if ident is None:
            return
        try:
            if method == "initialize":
                result = {"protocolVersion": message.get("params", {}).get("protocolVersion", "2025-03-26"), "capabilities": {"tools": {}}, "serverInfo": {"name": "task-matrix", "version": "1.0.0"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = message.get("params", {})
                value = call_tool(params.get("name"), params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "structuredContent": {"result": value}, "isError": False}
            else:
                raise KeyError(method)
            reply = {"jsonrpc": "2.0", "id": ident, "result": result}
        except KeyError as exc:
            reply = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"Method not found: {exc.args[0]}"}}
        except Exception as exc:
            if method == "tools/call":
                reply = {"jsonrpc": "2.0", "id": ident, "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
            else:
                reply = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": str(exc)}}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    for line in sys.stdin:
        try:
            respond(json.loads(line))
        except Exception:
            continue


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        return mcp_loop()
    port = int(os.environ.get("TASK_MATRIX_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
