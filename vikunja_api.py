"""
待办助手 API Client
===================
Handles authentication, task CRUD, and project listing for the server backend.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional


class VikunjaAPI:
    """Lightweight Vikunja REST API client."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.projects: list = []

    # ── auth ──────────────────────────────────────────────

    def login(self, username: str, password: str) -> bool:
        """Authenticate and store JWT token. Returns True on success."""
        try:
            resp = self._request("POST", "/login", {
                "username": username,
                "password": password,
            })
            self.token = resp["token"]
            self.user_id = resp.get("id")
            return True
        except VikunjaError as e:
            raise VikunjaError(f"登录失败: {e}")

    def token_valid(self) -> bool:
        """Quick check if stored token is still accepted."""
        if not self.token:
            return False
        try:
            self._request("GET", "/user")
            return True
        except VikunjaError:
            return False

    # ── projects ──────────────────────────────────────────

    def get_projects(self) -> list:
        """Return list of projects: [{"id": 1, "title": "Inbox"}, ...]"""
        self.projects = self._request("GET", "/projects")
        return self.projects

    def get_default_project_id(self) -> int:
        """Return the first project's id (usually Inbox)."""
        if not self.projects:
            self.get_projects()
        if self.projects:
            return self.projects[0]["id"]
        raise VikunjaError("没有找到项目，请先在 Vikunja 中创建一个项目")

    # ── tasks ─────────────────────────────────────────────

    def get_tasks(self, project_id: Optional[int] = None) -> list:
        """
        Fetch all tasks. If project_id given, return only that project's tasks.
        Returns list of task dicts:
          {id, title, priority, done, done_at, project_id, due_date, ...}
        """
        if project_id:
            # Get tasks via project endpoint for better filtering
            project = self._request("GET", f"/projects/{project_id}")
            # The project response includes view data but tasks are fetched separately
            # Fall back to getting all tasks and filtering
            all_tasks = self._request("GET", "/tasks")
            return [t for t in all_tasks if t.get("project_id") == project_id]
        return self._request("GET", "/tasks")

    def create_task(self, project_id: int, title: str,
                    priority: int = 1, description: str = "") -> dict:
        """Create a new task. priority: 0-5 (5=highest). Returns task dict."""
        return self._request("PUT", f"/projects/{project_id}/tasks", {
            "title": title,
            "priority": priority,
            "description": description,
        })

    def update_task(self, task_id: int, **fields) -> dict:
        """Partial-update a task. Pass fields like done=True, priority=3, title='...'."""
        return self._request("POST", f"/tasks/{task_id}", fields)

    def delete_task(self, task_id: int):
        """Delete a task permanently."""
        self._request("DELETE", f"/tasks/{task_id}")

    def toggle_done(self, task_id: int, done: bool) -> dict:
        """Mark task as done or undone."""
        return self.update_task(task_id, done=done)

    # ── internal ──────────────────────────────────────────

    def _request(self, method: str, path: str, data: dict = None) -> dict | list:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")
            if e.code == 401:
                raise TokenExpiredError(f"令牌已过期 (HTTP 401): {msg[:300]}")
            raise VikunjaError(f"HTTP {e.code}: {msg[:300]}")
        except urllib.error.URLError as e:
            raise VikunjaError(f"连接失败: {e.reason}")


class VikunjaError(Exception):
    pass


class TokenExpiredError(VikunjaError):
    """ Raised when the API returns 401 — token expired or invalid. """
    pass
