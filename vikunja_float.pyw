"""
待办助手 — Windows桌面悬浮任务窗
==================================
Always-on-top floating widget for task management.
View, add, and complete tasks grouped by priority.

Usage:
    python vikunja_float.pyw        # no console (double-click on Windows)
    python vikunja_float.py         # with console for debugging

Requires: customtkinter, pillow (optional, for tray icon)
"""

import json
import os
import sys
import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from vikunja_api import VikunjaAPI, VikunjaError, TokenExpiredError

# ═══════════════════════════════════════════════════════════
# Theme
# ═══════════════════════════════════════════════════════════

LIGHT_BG       = "#f8faff"   # 主背景 — 淡蓝白
LIGHT_SURFACE  = "#ffffff"   # 卡片/输入框白底
ACCENT_BLUE    = "#3b82f6"   # 主题蓝
ACCENT_LIGHT   = "#e0eeff"   # 淡蓝底色
ACCENT_HOVER   = "#d0e4ff"   # 悬停
BORDER_GRAY    = "#e5e7eb"   # 边框灰
TEXT_PRIMARY   = "#1e293b"   # 主文字
TEXT_SECONDARY = "#64748b"   # 次要文字
TEXT_MUTED     = "#94a3b8"   # 更淡文字

# ═══════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

PRIORITY_CONFIG = {
    5: {"label": "P0 · 紧急", "color": "#d63031", "bg": "#ffe0e0"},
    4: {"label": "P1 · 重要", "color": "#e17055", "bg": "#fff0e0"},
    3: {"label": "P1 · 重要", "color": "#e17055", "bg": "#fff0e0"},
    2: {"label": "P2 · 一般", "color": "#0984e3", "bg": "#e0efff"},
    1: {"label": "P2 · 一般", "color": "#0984e3", "bg": "#e0efff"},
    0: {"label": "P3 · 琐事", "color": "#636e72", "bg": "#f0f0f0"},
}

DEFAULT_CONFIG = {
    "base_url": "http://101.133.151.49:3456",
    "username": "",
    "token": "",
    "project_id": 0,
    "always_on_top": True,
    "refresh_interval": 60,
    "window_geometry": "360x520+100+100",
}


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return {**DEFAULT_CONFIG, **cfg}
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════
# Login Dialog
# ═══════════════════════════════════════════════════════════

class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, api: VikunjaAPI, config: dict):
        super().__init__(parent)
        self.api = api
        self.config = config
        self.result = None

        self.title("待办助手 · 登录")
        self.geometry("380x340")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=LIGHT_BG)

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 380) // 2
        y = (sh - 340) // 2
        self.geometry(f"380x340+{x}+{y}")

        # Header
        ctk.CTkLabel(self, text="🔐 待办助手", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="输入服务器地址和登录账号",
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY).pack(pady=(0, 15))

        # Server URL
        ctk.CTkLabel(self, text="服务器地址", anchor="w",
                     text_color=TEXT_SECONDARY).pack(padx=30, pady=(5, 0))
        self.url_entry = ctk.CTkEntry(self, width=300,
                                       placeholder_text="http://101.133.151.49:3456",
                                       fg_color=LIGHT_SURFACE, text_color=TEXT_PRIMARY,
                                       border_color=BORDER_GRAY)
        self.url_entry.pack(padx=30, pady=(0, 10))
        self.url_entry.insert(0, config.get("base_url", ""))

        # Username
        ctk.CTkLabel(self, text="用户名", anchor="w",
                     text_color=TEXT_SECONDARY).pack(padx=30, pady=(5, 0))
        self.user_entry = ctk.CTkEntry(self, width=300,
                                        placeholder_text="登录用户名",
                                        fg_color=LIGHT_SURFACE, text_color=TEXT_PRIMARY,
                                        border_color=BORDER_GRAY)
        self.user_entry.pack(padx=30, pady=(0, 10))
        self.user_entry.insert(0, config.get("username", ""))

        # Password
        ctk.CTkLabel(self, text="密码", anchor="w",
                     text_color=TEXT_SECONDARY).pack(padx=30, pady=(5, 0))
        self.pass_entry = ctk.CTkEntry(self, width=300, show="●",
                                        placeholder_text="登录密码",
                                        fg_color=LIGHT_SURFACE, text_color=TEXT_PRIMARY,
                                        border_color=BORDER_GRAY)
        self.pass_entry.pack(padx=30, pady=(0, 10))

        # Status
        self.status_label = ctk.CTkLabel(self, text="", text_color="#d63031")
        self.status_label.pack(pady=(5, 0))

        # Login button — white text on blue, always visible
        self.login_btn = ctk.CTkButton(self, text="登  录", width=200, height=38,
                                        fg_color=ACCENT_BLUE, hover_color="#2563eb",
                                        text_color="white",
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        command=self._do_login)
        self.login_btn.pack(pady=(12, 10))

        self.pass_entry.bind("<Return>", lambda e: self._do_login())

    def _do_login(self):
        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get().strip()

        if not url or not user or not pwd:
            self.status_label.configure(text="请填写所有字段")
            return

        self.login_btn.configure(text="登录中...", state="disabled")
        self.status_label.configure(text="正在连接...", text_color=TEXT_SECONDARY)
        self.update()

        def login_thread():
            try:
                self.api.base_url = url.rstrip("/") + "/api/v1"
                self.api.login(user, pwd)
                self.after(0, self._login_success)
            except VikunjaError as e:
                self.after(0, lambda: self._login_fail(str(e)))

        threading.Thread(target=login_thread, daemon=True).start()

    def _login_success(self):
        self.config["base_url"] = self.url_entry.get().strip()
        self.config["username"] = self.user_entry.get().strip()
        self.config["token"] = self.api.token
        save_config(self.config)
        self.result = True
        self.destroy()

    def _login_fail(self, msg):
        self.login_btn.configure(text="登  录", state="normal")
        self.status_label.configure(text=msg, text_color="#d63031")


# ═══════════════════════════════════════════════════════════
# Settings Dialog
# ═══════════════════════════════════════════════════════════

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, config: dict, refresh_callback=None):
        super().__init__(parent)
        self.config = config
        self.refresh_callback = refresh_callback

        self.title("⚙️ 设置")
        self.geometry("340x280")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=LIGHT_BG)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 340) // 2
        y = (sh - 280) // 2
        self.geometry(f"340x280+{x}+{y}")

        ctk.CTkLabel(self, text="设置", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(15, 10))

        # Refresh interval
        frame1 = ctk.CTkFrame(self, fg_color="transparent")
        frame1.pack(padx=20, pady=5, fill="x")
        ctk.CTkLabel(frame1, text="自动刷新 (秒):", text_color=TEXT_PRIMARY).pack(side="left")
        self.refresh_var = ctk.StringVar(value=str(config.get("refresh_interval", 60)))
        ctk.CTkEntry(frame1, width=60, textvariable=self.refresh_var,
                     fg_color=LIGHT_SURFACE, border_color=BORDER_GRAY).pack(side="right")

        # Always on top
        frame2 = ctk.CTkFrame(self, fg_color="transparent")
        frame2.pack(padx=20, pady=5, fill="x")
        self.ontop_var = ctk.BooleanVar(value=config.get("always_on_top", True))
        ctk.CTkCheckBox(frame2, text="窗口置顶", variable=self.ontop_var).pack(side="left")

        ctk.CTkLabel(self, text="").pack()  # spacer

        self.status_label = ctk.CTkLabel(self, text="", text_color="green")
        self.status_label.pack()

        ctk.CTkButton(self, text="保存并刷新", width=160,
                      fg_color=ACCENT_BLUE, hover_color="#2563eb",
                      command=self._save).pack(pady=(5, 5))
        ctk.CTkButton(self, text="重新登录...", width=160,
                      fg_color="transparent", text_color=ACCENT_BLUE,
                      border_width=1, border_color=ACCENT_BLUE,
                      hover_color=ACCENT_LIGHT,
                      command=self._relogin).pack(pady=(0, 10))

    def _save(self):
        try:
            interval = int(self.refresh_var.get())
            if interval < 10:
                interval = 10
        except ValueError:
            interval = 60

        self.config["refresh_interval"] = interval
        self.config["always_on_top"] = self.ontop_var.get()
        save_config(self.config)

        self.status_label.configure(text="✅ 已保存")
        if self.refresh_callback:
            self.refresh_callback()

    def _relogin(self):
        self.config["token"] = ""
        save_config(self.config)
        self.destroy()
        if self.refresh_callback:
            self.refresh_callback()


# ═══════════════════════════════════════════════════════════
# Main Floating Window
# ═══════════════════════════════════════════════════════════

class TodoFloat(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Load config
        self.config = load_config()
        self.api = VikunjaAPI(self.config["base_url"])
        self.api.token = self.config.get("token", "")
        self.api.user_id = None
        self.tasks_data = []
        self.task_widgets = {}
        self.project_id = self.config.get("project_id", 0)
        self.auto_refresh_id = None
        self._drag_x = 0
        self._drag_y = 0
        self.collapsed = False
        self._expanded_geometry = None

        # Window setup — no native title bar
        self.title("待办助手")
        geo = self.config.get("window_geometry", "360x520+100+100")
        # Guard against corrupted geometry (e.g. collapsed state was saved)
        try:
            parts = geo.replace("+", "x").split("x")
            _, h = int(parts[0]), int(parts[1])
            if h < 100:
                geo = "360x520+100+100"
        except (ValueError, IndexError):
            geo = "360x520+100+100"
        self.geometry(geo)
        self.overrideredirect(True)          # remove native title bar
        self.attributes("-topmost", self.config.get("always_on_top", True))
        self.configure(fg_color=LIGHT_BG)

        # Shadow/border via a slightly larger dark frame
        self._shadow = ctk.CTkFrame(self, fg_color=BORDER_GRAY, corner_radius=12)
        self._shadow.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Inner container
        self._inner = ctk.CTkFrame(self._shadow, fg_color=LIGHT_BG, corner_radius=10)
        self._inner.place(relx=0.002, rely=0.003, relwidth=0.996, relheight=0.994)

        # Mouse-drag on title bar
        self.bind("<Button-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_move)

        # Build UI inside _inner
        self._build_ui()

        # Focus tweak — allow keyboard after overrideredirect
        self.after(100, self._force_focus)

        # Load data
        self._auto_login_or_prompt()

    def _force_focus(self):
        """Ensure window can receive keyboard focus despite overrideredirect."""
        try:
            self.focus_force()
        except Exception:
            pass

    # ── window dragging ─────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    # ── UI construction ─────────────────────────────────

    def _build_ui(self):
        """Build the complete UI layout inside _inner."""

        # ---- Title bar (draggable) ----
        self.title_frame = ctk.CTkFrame(self._inner, height=40, corner_radius=0,
                                         fg_color=ACCENT_BLUE)
        self.title_frame.pack(fill="x", padx=0, pady=0)
        self.title_frame.pack_propagate(False)

        ctk.CTkLabel(self.title_frame, text="📋 待办助手",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").pack(side="left", padx=14, pady=8)

        self.connection_dot = ctk.CTkLabel(self.title_frame, text="●",
                                            text_color="#bfdbfe",
                                            font=ctk.CTkFont(size=10))
        self.connection_dot.pack(side="left", padx=(0, 10))

        # Collapse button
        self.collapse_btn = ctk.CTkButton(self.title_frame, text="▼", width=32, height=28,
                                           fg_color="transparent",
                                           text_color="#dbeafe",
                                           hover_color="#93c5fd",
                                           font=ctk.CTkFont(size=10),
                                           command=self._toggle_collapse)
        self.collapse_btn.pack(side="left", padx=(0, 2), pady=6)

        # Close button (×) — replaces native title bar buttons
        self.close_btn = ctk.CTkButton(self.title_frame, text="✕", width=36, height=28,
                                        fg_color="transparent",
                                        text_color="#dbeafe",
                                        hover_color="#93c5fd",
                                        font=ctk.CTkFont(size=14),
                                        command=self._on_close)
        self.close_btn.pack(side="right", padx=(0, 6), pady=6)

        self.refresh_btn = ctk.CTkButton(self.title_frame, text="🔄", width=32, height=28,
                                          fg_color="transparent",
                                          text_color="#dbeafe",
                                          hover_color="#93c5fd",
                                          command=self.refresh_tasks)
        self.refresh_btn.pack(side="right", padx=(0, 2), pady=6)

        self.settings_btn = ctk.CTkButton(self.title_frame, text="⚙", width=32, height=28,
                                           fg_color="transparent",
                                           text_color="#dbeafe",
                                           hover_color="#93c5fd",
                                           command=self.open_settings)
        self.settings_btn.pack(side="right", padx=(0, 2), pady=6)

        # ---- Collapsible content wrapper ----
        self.content_frame = ctk.CTkFrame(self._inner, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        # ---- Status bar ----
        self.status_bar = ctk.CTkFrame(self.content_frame, height=28, corner_radius=0,
                                        fg_color=ACCENT_LIGHT)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)
        self.status_label = ctk.CTkLabel(self.status_bar, text="加载中...",
                                          font=ctk.CTkFont(size=11),
                                          text_color=TEXT_SECONDARY)
        self.status_label.pack(side="left", padx=12, pady=4)

        # ---- Task list (scrollable) ----
        self.task_scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.task_scroll.pack(fill="both", expand=True, padx=4, pady=(2, 0))

        # ---- Quick-add bar ----
        self.add_frame = ctk.CTkFrame(self.content_frame, height=44, corner_radius=0,
                                       fg_color=LIGHT_SURFACE)
        self.add_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        self.add_frame.pack_propagate(False)

        # Priority dropdown
        self.prio_var = ctk.StringVar(value="P1")
        self.prio_menu = ctk.CTkOptionMenu(
            self.add_frame, values=["P0", "P1", "P2", "P3"],
            variable=self.prio_var, width=50, height=28,
            fg_color=LIGHT_SURFACE, button_color=ACCENT_LIGHT,
            text_color=TEXT_PRIMARY, button_hover_color=ACCENT_HOVER,
            command=self._on_prio_change
        )
        self.prio_menu.pack(side="left", padx=(8, 4), pady=8)

        # Task entry
        self.add_entry = ctk.CTkEntry(self.add_frame, placeholder_text="添加任务...",
                                       height=28, fg_color="#f1f5f9",
                                       text_color=TEXT_PRIMARY,
                                       border_width=0, corner_radius=8)
        self.add_entry.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=8)
        self.add_entry.bind("<Return>", lambda e: self.add_task())

        # Add button
        self.add_btn = ctk.CTkButton(self.add_frame, text="＋", width=32, height=28,
                                      fg_color=ACCENT_BLUE, hover_color="#2563eb",
                                      text_color="white",
                                      font=ctk.CTkFont(size=16),
                                      command=self.add_task)
        self.add_btn.pack(side="right", padx=(0, 8), pady=8)

    # ── Data loading ────────────────────────────────────

    def _auto_login_or_prompt(self):
        """Check stored token or show login dialog."""
        if self.api.token:
            if self.api.token_valid():
                self._on_connected()
                return
            else:
                self.status_label.configure(text="令牌过期，请重新登录")

        self.after(500, self._show_login)

    def _show_login(self):
        dialog = LoginDialog(self, self.api, self.config)
        self.wait_window(dialog)
        if dialog.result:
            self._on_connected()
        else:
            self.status_label.configure(text="未登录 — 点击 ⚙ 重新登录")
            self.connection_dot.configure(text_color="#d63031")

    def _on_connected(self):
        """Called after successful login."""
        self.connection_dot.configure(text_color="#22c55e")

        try:
            projects = self.api.get_projects()
            if projects and not self.project_id:
                self.project_id = projects[0]["id"]
                self.config["project_id"] = self.project_id
                save_config(self.config)
            proj_name = next((p["title"] for p in projects if p["id"] == self.project_id), "待办助手")
            self.status_label.configure(text=f"📋 {proj_name}")
        except VikunjaError:
            self.status_label.configure(text="已连接")

        self.refresh_tasks()
        self._start_auto_refresh()

    # ── Task display ────────────────────────────────────

    def refresh_tasks(self):
        """Fetch tasks from server and rebuild the list."""
        if not self.api.token:
            return

        def fetch():
            try:
                tasks = self.api.get_tasks(project_id=self.project_id) if self.project_id else self.api.get_tasks()
                tasks.sort(key=lambda t: (t.get("done", False), -t.get("priority", 0), t.get("title", "")))
                self.after(0, lambda: self._render_tasks(tasks))
            except TokenExpiredError:
                self.after(0, self._handle_token_expired)
            except VikunjaError as e:
                self.after(0, lambda: self._show_error(f"刷新失败: {e}"))
            except Exception as e:
                self.after(0, lambda: self._show_error(f"刷新失败(未知): {e}"))

        self.refresh_btn.configure(text="⏳", state="disabled")
        threading.Thread(target=fetch, daemon=True).start()

    def _render_tasks(self, tasks: list):
        """Rebuild the task list UI from task data."""
        self.tasks_data = tasks
        self.task_widgets.clear()

        for w in self.task_scroll.winfo_children():
            w.destroy()

        if not tasks:
            empty_label = ctk.CTkLabel(self.task_scroll,
                                        text="🎉 没有任务\n使用下方输入框添加",
                                        font=ctk.CTkFont(size=13),
                                        text_color=TEXT_MUTED)
            empty_label.pack(pady=40)
            self.refresh_btn.configure(text="🔄", state="normal")
            self._update_status_counts(tasks)
            return

        grouped = {5: [], 4: [], 3: [], 2: [], 1: [], 0: []}
        for t in tasks:
            prio = t.get("priority", 0)
            grouped.setdefault(prio, []).append(t)

        for prio in [5, 4, 3, 2, 1, 0]:
            group_tasks = grouped[prio]
            if not group_tasks:
                continue

            pconfig = PRIORITY_CONFIG.get(prio, PRIORITY_CONFIG[0])
            undone = sum(1 for t in group_tasks if not t.get("done"))

            # Group header
            header_frame = ctk.CTkFrame(self.task_scroll, fg_color=pconfig["bg"],
                                         corner_radius=6, height=28)
            header_frame.pack(fill="x", padx=2, pady=(8, 2))
            header_frame.pack_propagate(False)
            ctk.CTkLabel(header_frame, text=f"● {pconfig['label']}  ({undone})",
                         text_color=pconfig["color"],
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).pack(side="left", padx=10, pady=4)

            for task in group_tasks:
                self._add_task_row(task, pconfig)

        self.refresh_btn.configure(text="🔄", state="normal")
        self._update_status_counts(tasks)

    def _add_task_row(self, task: dict, pconfig: dict):
        """Add a single task row to the scrollable frame."""
        tid = task["id"]
        done = task.get("done", False)
        title = task.get("title", "")

        row = ctk.CTkFrame(self.task_scroll, fg_color="transparent", height=30)
        row.pack(fill="x", padx=4, pady=1)
        row.pack_propagate(False)

        cb_var = ctk.BooleanVar(value=done)
        cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=20,
                             command=lambda t=tid, v=cb_var: self._toggle_task(t, v.get()))
        cb.pack(side="left", padx=(8, 4), pady=3)

        title_color = pconfig["color"] if not done else TEXT_MUTED
        title_font = ctk.CTkFont(size=12, overstrike=done)
        label = ctk.CTkLabel(row, text=title, anchor="w",
                             text_color=title_color, font=title_font)
        label.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=3)

        del_btn = ctk.CTkButton(row, text="×", width=22, height=22,
                                fg_color="transparent", text_color=TEXT_MUTED,
                                hover_color="#ffe0e0",
                                command=lambda t=tid: self._delete_task(t))
        del_btn.pack(side="right", padx=(0, 4))

        self.task_widgets[tid] = {"row": row, "cb_var": cb_var, "label": label}

    def _update_status_counts(self, tasks: list):
        undone = sum(1 for t in tasks if not t.get("done"))
        total = len(tasks)
        proj_name = "待办助手"
        try:
            for p in self.api.projects:
                if p["id"] == self.project_id:
                    proj_name = p["title"]
                    break
        except Exception:
            pass
        self.status_label.configure(text=f"📋 {proj_name}  ·  {undone}/{total} 未完成")

    # ── Token management ────────────────────────────────

    def _handle_token_expired(self):
        """Called when API returns 401 — stop refresh and show login."""
        self.api.token = ""
        self.config["token"] = ""
        save_config(self.config)
        self.connection_dot.configure(text_color="#d63031")
        self.status_label.configure(text="⚠️ 令牌已过期，请重新登录")
        if self.auto_refresh_id:
            self.after_cancel(self.auto_refresh_id)
            self.auto_refresh_id = None
        self._show_login()

    # ── Task actions ────────────────────────────────────

    def _toggle_task(self, task_id: int, done: bool):
        # Optimistic: toggle immediately in local data
        for t in self.tasks_data:
            if t["id"] == task_id:
                t["done"] = done
                break
        self._render_tasks(self.tasks_data)

        def do_toggle():
            try:
                self.api.toggle_done(task_id, done)
                # No refresh needed — already correct. But refresh to sync
                # any server-side changes (e.g. done_at timestamp).
                self.after(0, self.refresh_tasks)
            except VikunjaError as e:
                # Revert and refresh
                self.after(0, self.refresh_tasks)
                self.after(0, lambda: self._show_error(f"操作失败: {e}"))

        threading.Thread(target=do_toggle, daemon=True).start()

    def add_task(self):
        """Add a new task from the quick-add bar."""
        title = self.add_entry.get().strip()
        if not title:
            return

        if not self.api.token:
            self._handle_token_expired()
            return

        prio_display = self.prio_var.get()
        prio_map = {"P0": 5, "P1": 3, "P2": 1, "P3": 0}
        priority = prio_map.get(prio_display, 1)

        self.add_entry.delete(0, "end")
        self.add_btn.configure(text="...", state="disabled")

        # Optimistic: insert temporary task immediately
        temp_id = -int(time.time() * 1000)  # negative ID → temporary
        optimistic = {
            "id": temp_id, "title": title, "priority": priority,
            "done": False, "project_id": self.project_id, "description": "",
        }
        self.tasks_data.insert(0, optimistic)
        self._render_tasks(self.tasks_data)

        def do_add():
            try:
                pid = self.project_id or self.api.get_default_project_id()
                self.api.create_task(pid, title, priority=priority)
                self.after(0, self.refresh_tasks)  # sync real data from server
            except TokenExpiredError:
                self.after(0, self._handle_token_expired)
            except VikunjaError as e:
                self.after(0, lambda: self._revert_and_refresh(temp_id))
                self.after(0, lambda: messagebox.showerror("添加失败", str(e)))
            except Exception as e:
                self.after(0, lambda: self._revert_and_refresh(temp_id))
                self.after(0, lambda: messagebox.showerror("添加失败",
                    f"未知错误: {e}\n\n请检查网络连接和服务器状态"))
            finally:
                self.after(0, lambda: self.add_btn.configure(text="＋", state="normal"))

        threading.Thread(target=do_add, daemon=True).start()

    def _revert_and_refresh(self, temp_id: int):
        """Remove optimistic task and refresh from server."""
        self.tasks_data = [t for t in self.tasks_data if t.get("id") != temp_id]
        self.refresh_tasks()

    def _delete_task(self, task_id: int):
        if not messagebox.askyesno("确认删除", "确定要删除这个任务吗？此操作不可恢复。"):
            return

        # Optimistic: remove from local data immediately
        self.tasks_data = [t for t in self.tasks_data if t["id"] != task_id]
        self._render_tasks(self.tasks_data)

        def do_delete():
            try:
                self.api.delete_task(task_id)
            except VikunjaError as e:
                # Restore and refresh
                self.after(0, self.refresh_tasks)
                self.after(0, lambda: self._show_error(f"删除失败: {e}"))

        threading.Thread(target=do_delete, daemon=True).start()

    # ── Settings ───────────────────────────────────────

    def open_settings(self):
        dialog = SettingsDialog(self, self.config, refresh_callback=self._on_settings_changed)
        self.wait_window(dialog)

    def _on_settings_changed(self):
        self.attributes("-topmost", self.config.get("always_on_top", True))
        self._start_auto_refresh()
        if not self.config.get("token"):
            self.api.token = ""
            self._show_login()

    # ── Auto-refresh ───────────────────────────────────

    def _start_auto_refresh(self):
        if self.auto_refresh_id:
            self.after_cancel(self.auto_refresh_id)
        interval = self.config.get("refresh_interval", 60) * 1000
        self._schedule_refresh(interval)

    def _schedule_refresh(self, interval_ms):
        self.refresh_tasks()
        self.auto_refresh_id = self.after(interval_ms, lambda: self._schedule_refresh(interval_ms))

    # ── Window management ──────────────────────────────

    def _toggle_collapse(self):
        """Fold window to title-bar only, or expand back."""
        if self.collapsed:
            # Expand
            self.collapsed = False
            self.collapse_btn.configure(text="▼")
            self.content_frame.pack(fill="both", expand=True)
            if self._expanded_geometry:
                self.geometry(self._expanded_geometry)
        else:
            # Collapse — save geometry, hide content, shrink to title bar
            self.collapsed = True
            self.collapse_btn.configure(text="▲")
            self._expanded_geometry = self.geometry()
            self.content_frame.pack_forget()
            # Derive width & position from the saved expanded geometry string
            # (more reliable than winfo_width which may drift)
            parts = self._expanded_geometry.replace("+", "x").split("x")
            w, _, x, y = parts[0], parts[1], parts[2], parts[3]
            self.geometry(f"{w}x44+{x}+{y}")

    def _on_close(self):
        """Save window geometry and hide to system tray (or quit)."""
        geo = self._expanded_geometry if self.collapsed else self.geometry()
        self.config["window_geometry"] = geo
        save_config(self.config)

        try:
            self.withdraw()
            self._create_tray()
        except Exception:
            self.iconify()

    def _create_tray(self):
        """Minimize to system tray. Requires pystray + pillow."""
        try:
            import pystray
            from PIL import Image, ImageDraw

            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill="#3b82f6")
            draw.text((20, 20), "待", fill="white")

            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self._show_from_tray, default=True),
                pystray.MenuItem("刷新任务", self.refresh_tasks),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._quit_app),
            )
            self.tray_icon = pystray.Icon("todo_float", img, "待办助手", menu)

            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except ImportError:
            self.iconify()

    def _show_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self):
        if hasattr(self, "tray_icon"):
            self.tray_icon.stop()
        self.destroy()

    # ── Error display ──────────────────────────────────

    def _show_error(self, msg: str):
        self.status_label.configure(text=f"⚠️ {msg}", text_color="#d63031")
        self.after(5000, lambda: self._update_status_counts(self.tasks_data))

    def _on_prio_change(self, value):
        colors = {"P0": "#d63031", "P1": "#e17055", "P2": "#0984e3", "P3": "#636e72"}
        self.prio_menu.configure(fg_color=colors.get(value, LIGHT_SURFACE))


# ═══════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════

def main():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = TodoFloat()
    app.mainloop()


if __name__ == "__main__":
    main()
