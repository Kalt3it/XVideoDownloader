"""Chinese Windows desktop interface and frozen executable entry point."""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk, font as tkfont

from core import APP_VERSION, InputError, load_settings, normalize_url, save_settings, settings_file, validate_proxy
from i18n import FONT_FAMILIES, LANGUAGE_NAMES, TEXT, normalize_language, translate
from widgets import FlatScrollbar


def worker_command(request: Path, events: Path) -> list[str]:
    args = ["--worker", str(request), str(events)]
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def stop_process_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=12, check=False)
    elif process.poll() is None:
        process.terminate()
    if process.poll() is None:
        process.kill()


def human_bytes(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024


class App:
    def __init__(self, root: tk.Tk, settings_path: Path | None = None):
        self.root = root
        self.settings_path = settings_path or settings_file()
        settings = load_settings(self.settings_path)
        self.language = settings["language"]
        self.language_var = tk.StringVar(value=LANGUAGE_NAMES[self.language])
        self.text_vars = {}
        self.fonts = {name: tkfont.Font(root=root, family=FONT_FAMILIES[self.language], size=size, weight=weight)
                      for name, size, weight in (("body", 10, "normal"), ("hint", 9, "normal"),
                        ("title", 20, "bold"), ("section", 11, "bold"), ("status", 12, "bold"))}
        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=settings["folder"])
        self.proxy_var = tk.StringVar(value=settings["proxy"])
        self.cookie_var = tk.StringVar()
        self.status_state = ("ready", {})
        self.detail_state = ("ready_detail", {})
        self.last_display_event = None
        self.retry = False
        self.status_var = tk.StringVar(value=self.t("ready"))
        self.detail_var = tk.StringVar(value=self.t("ready_detail"))
        self.percent_var = tk.StringVar(value="")
        self.process = None
        self.job_dir = None
        self.event_offset = 0
        self.final_event = None
        self.last_files = []
        self.cancelled = False
        self.closing = False
        self.advanced_open = False
        self.poll_id = None
        self.stop_thread = None
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        root = self.root
        root.title(self.t("title"))
        root.geometry("820x670")
        root.minsize(620, 440)
        root.configure(bg="#f3f6fb")
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).parent / "build" / "assets")) / "app.ico"
        if icon.is_file():
            root.iconbitmap(str(icon))
        root.option_add("*Font", self.fonts["body"])
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=self.fonts["body"])
        # Drop the theme's bevel and focus-box elements from every button.
        style.layout("TButton", [("Button.padding", {"sticky": "nswe", "children": [
            ("Button.label", {"sticky": "nswe"}),
        ]})])
        style.configure("TFrame", background="#f3f6fb")
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background="#f3f6fb", foreground="#172338")
        style.configure("Card.TLabel", background="white", foreground="#172338")
        style.configure("Hint.TLabel", background="white", foreground="#68758a", font=self.fonts["hint"])
        style.configure("TButton", padding=(15, 9), background="#e9eef5", foreground="#27354b", borderwidth=0)
        style.map("TButton", background=[("disabled", "#eef2f7"), ("pressed", "#d6e1f0"),
                                          ("active", "#dce5f2"), ("focus", "#dce5f2")],
                  foreground=[("disabled", "#9aa5b5")])
        style.configure("Accent.TButton", background="#2563eb", foreground="white", font=self.fonts["section"])
        style.map("Accent.TButton", background=[("disabled", "#b5c7eb"), ("pressed", "#1e40af"),
                                                 ("active", "#1d4ed8"), ("focus", "#1d4ed8")],
                  foreground=[("disabled", "#f6f8fc")])
        style.configure("Quiet.TButton", background="#f3f6fb", foreground="#526783", padding=(10, 7))
        style.map("Quiet.TButton", background=[("active", "#e7edf6"), ("focus", "#e7edf6")])
        style.configure("TEntry", padding=10, fieldbackground="white", borderwidth=1,
                        bordercolor="#dfe6ef", lightcolor="white", darkcolor="white", relief="flat")
        style.map("TEntry", bordercolor=[("focus", "#93b5f8")],
                  lightcolor=[("focus", "white")], darkcolor=[("focus", "white")])
        style.configure("Blue.Horizontal.TProgressbar", background="#2563eb", troughcolor="#e8eef8",
                        borderwidth=0, thickness=6, lightcolor="#2563eb", darkcolor="#2563eb")
        style.configure("Language.TCombobox", padding=(10, 5), background="white", fieldbackground="white",
                        foreground="#526783", bordercolor="#dfe6ef", lightcolor="#dfe6ef", darkcolor="#dfe6ef",
                        arrowcolor="#708098", borderwidth=1, arrowsize=12)
        style.map("Language.TCombobox", fieldbackground=[("readonly", "white")],
                  selectbackground=[("readonly", "white")], selectforeground=[("readonly", "#526783")])

        toolbar = ttk.Frame(root, padding=(26, 10, 22, 0))
        toolbar.pack(fill="x")
        self.language_combo = ttk.Combobox(toolbar, textvariable=self.language_var,
            values=list(LANGUAGE_NAMES.values()), state="readonly", width=13, style="Language.TCombobox")
        self.language_combo.pack(side="right")
        self.language_combo.bind("<<ComboboxSelected>>", lambda _event: self.set_language(
            next(code for code, name in LANGUAGE_NAMES.items() if name == self.language_var.get())))
        ttk.Label(toolbar, textvariable=self.textvar("language"), foreground="#708098").pack(side="right", padx=(0, 10))

        viewport = ttk.Frame(root)
        viewport.pack(fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(viewport, background="#f3f6fb", highlightthickness=0, borderwidth=0,
                                       yscrollincrement=22)
        self.scrollbar = FlatScrollbar(viewport, command=self.scroll_canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        shell = ttk.Frame(self.scroll_canvas, padding=(26, 23))
        inner = self.scroll_canvas.create_window((0, 0), window=shell, anchor="nw")
        shell.bind("<Configure>", lambda _event: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))
        def resize_content(event):
            self.scroll_canvas.itemconfigure(inner, width=event.width)
            if hasattr(self, "detail_label"):
                self.detail_label.configure(wraplength=max(220, event.width - 100))
            if hasattr(self, "link_hint_label"):
                self.link_hint_label.configure(wraplength=max(220, event.width - 110))
            for name in ("proxy_hint_label", "cookie_hint_label"):
                if hasattr(self, name):
                    getattr(self, name).configure(wraplength=max(160, event.width - 250))
        self.scroll_canvas.bind("<Configure>", resize_content)
        root.bind("<MouseWheel>", self.scroll_wheel)
        root.bind("<Next>", lambda _event: self.scroll_canvas.yview_scroll(1, "pages"))
        root.bind("<Prior>", lambda _event: self.scroll_canvas.yview_scroll(-1, "pages"))
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 20))
        tk.Label(header, text="X", bg="#152033", fg="white", font=("Segoe UI", 25, "bold"),
                 width=2, pady=2).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side="left")
        ttk.Label(titles, textvariable=self.textvar("title"), font=self.fonts["title"]).pack(anchor="w")
        ttk.Label(titles, textvariable=self.textvar("subtitle"), foreground="#708098").pack(anchor="w", pady=(3, 0))
        ttk.Label(header, text=f"v{APP_VERSION}", foreground="#8390a3").pack(side="right", anchor="n", pady=8)

        card = ttk.Frame(shell, style="Card.TFrame", padding=22)
        card.pack(fill="x")
        ttk.Label(card, textvariable=self.textvar("post_link"), style="Card.TLabel", font=self.fonts["section"]).pack(anchor="w")
        link_row = ttk.Frame(card, style="Card.TFrame")
        link_row.pack(fill="x", pady=(10, 5))
        self.url_entry = ttk.Entry(link_row, textvariable=self.url_var, font=("Segoe UI", 11))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.paste_button = ttk.Button(link_row, textvariable=self.textvar("paste"), command=self.paste)
        self.paste_button.pack(side="right")
        self.link_hint_label = ttk.Label(card, textvariable=self.textvar("link_hint"), style="Hint.TLabel", wraplength=620)
        self.link_hint_label.pack(anchor="w", fill="x")

        ttk.Label(card, textvariable=self.textvar("save_to"), style="Card.TLabel", font=self.fonts["section"]).pack(anchor="w", pady=(20, 0))
        folder_row = ttk.Frame(card, style="Card.TFrame")
        folder_row.pack(fill="x", pady=(10, 0))
        self.folder_entry = ttk.Entry(folder_row, textvariable=self.folder_var)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.browse_button = ttk.Button(folder_row, textvariable=self.textvar("choose_folder"), command=self.choose_folder)
        self.browse_button.pack(side="right")

        self.advanced_button = ttk.Button(shell, text="＋ " + self.t("advanced"), style="Quiet.TButton", command=self.toggle_advanced)
        self.advanced_button.pack(anchor="w", pady=(12, 10))
        self.advanced_frame = ttk.Frame(shell, padding=(12, 2))
        ttk.Label(self.advanced_frame, textvariable=self.textvar("proxy")).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        self.proxy_entry = ttk.Entry(self.advanced_frame, textvariable=self.proxy_var)
        self.proxy_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self.proxy_hint_label = ttk.Label(self.advanced_frame, textvariable=self.textvar("proxy_hint"), foreground="#708098",
                                         font=self.fonts["hint"], wraplength=400)
        self.proxy_hint_label.grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Label(self.advanced_frame, textvariable=self.textvar("cookies")).grid(row=2, column=0, sticky="w", padx=(0, 12), pady=(8, 4))
        self.cookie_entry = ttk.Entry(self.advanced_frame, textvariable=self.cookie_var)
        self.cookie_entry.grid(row=2, column=1, sticky="ew", pady=(8, 4))
        self.cookie_button = ttk.Button(self.advanced_frame, textvariable=self.textvar("choose"), command=self.choose_cookies)
        self.cookie_button.grid(row=2, column=2, padx=(10, 0), pady=(8, 4))
        self.cookie_hint_label = ttk.Label(self.advanced_frame, textvariable=self.textvar("cookie_hint"),
                                         foreground="#708098", font=self.fonts["hint"], wraplength=400)
        self.cookie_hint_label.grid(row=3, column=1, columnspan=2, sticky="w")
        self.advanced_frame.columnconfigure(1, weight=1)

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(7, 18))
        self.start_button = ttk.Button(actions, text=self.t("start"), style="Accent.TButton", command=self.start_download)
        self.start_button.pack(side="left", ipadx=22)
        self.cancel_button = ttk.Button(actions, textvariable=self.textvar("cancel"), command=self.cancel_download, state="disabled")
        self.cancel_button.pack(side="left", padx=10)
        self.open_button = ttk.Button(actions, textvariable=self.textvar("open_folder"), command=self.open_folder)
        self.open_button.pack(side="right")

        self.status_frame = ttk.Frame(shell, style="Card.TFrame", padding=20)
        self.status_frame.pack(fill="x")
        status_row = ttk.Frame(self.status_frame, style="Card.TFrame")
        status_row.pack(fill="x")
        ttk.Label(status_row, textvariable=self.status_var, style="Card.TLabel", font=self.fonts["status"], wraplength=520).pack(side="left", fill="x", expand=True)
        ttk.Label(status_row, textvariable=self.percent_var, style="Hint.TLabel").pack(side="right")
        self.progress = ttk.Progressbar(self.status_frame, style="Blue.Horizontal.TProgressbar", maximum=100)
        self.progress.pack(fill="x", pady=(14, 11))
        self.detail_label = ttk.Label(self.status_frame, textvariable=self.detail_var, style="Hint.TLabel", wraplength=660, justify="left")
        self.detail_label.pack(anchor="w", fill="x")
        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Label(footer, textvariable=self.textvar("footer"), foreground="#7c899c", font=self.fonts["hint"], wraplength=420).pack(side="left")
        self.help_button = ttk.Button(footer, textvariable=self.textvar("help"), style="Quiet.TButton", command=self.help)
        self.help_button.pack(side="right")
        self.root.bind("<Return>", self.handle_return)
        self.url_entry.focus_set()

    def handle_return(self, event):
        if event.widget is not self.language_combo:
            self.start_download()

    def t(self, key, **params):
        return translate(self.language, key, **params)

    def textvar(self, key):
        if key not in self.text_vars:
            self.text_vars[key] = tk.StringVar(value=self.t(key))
        return self.text_vars[key]

    def set_status(self, key, **params):
        self.status_state = (key, params)
        self.status_var.set(self.t(key, **params))

    def set_detail(self, key, **params):
        self.detail_state = (key, params)
        self.last_display_event = None
        self.detail_var.set(self.t(key, **params))

    def set_language(self, language):
        self.language = normalize_language(language)
        self.language_var.set(LANGUAGE_NAMES[self.language])
        self.root.title(self.t("title"))
        for key, variable in self.text_vars.items():
            variable.set(self.t(key))
        for font in self.fonts.values():
            font.configure(family=FONT_FAMILIES[self.language])
        self.start_button.configure(text=self.t("retry" if self.retry else "start"))
        self.advanced_button.configure(text=("－ " if self.advanced_open else "＋ ") + self.t("advanced"))
        key, params = self.status_state
        self.status_var.set(self.t(key, **params))
        if self.last_display_event:
            self.consume(self.last_display_event)
        else:
            key, params = self.detail_state
            if key:
                self.detail_var.set(self.t(key, **params))
        self.remember()

    def scroll_wheel(self, event):
        if self.scroll_canvas.yview() == (0.0, 1.0):
            return
        if event.delta:
            units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
            self.scroll_canvas.yview_scroll(units * 3, "units")
        return "break"

    def paste(self):
        try:
            self.url_var.set(self.root.clipboard_get().strip())
        except tk.TclError:
            self.set_status("clipboard_empty")

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title=self.t("folder_dialog"), initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.remember()

    def choose_cookies(self):
        path = filedialog.askopenfilename(parent=self.root, title=self.t("cookies_dialog"),
                                          filetypes=[(self.t("cookies_text"), "*.txt"), (self.t("all_files"), "*.*")])
        if path:
            self.cookie_var.set(path)

    def toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        if self.advanced_open:
            self.advanced_frame.pack(fill="x", after=self.advanced_button, pady=(0, 8))
        else:
            self.advanced_frame.pack_forget()
        self.advanced_button.configure(text=("－ " if self.advanced_open else "＋ ") + self.t("advanced"))

    def remember(self):
        try:
            try:
                proxy = validate_proxy(self.proxy_var.get())
            except InputError:
                # Editing a proxy must not prevent saving an unrelated language choice.
                proxy = load_settings(self.settings_path)["proxy"]
            save_settings(self.settings_path, {"folder": self.folder_var.get(), "proxy": proxy, "language": self.language})
        except (OSError, ValueError):
            # Downloading remains usable even when preferences cannot be saved.
            pass

    def set_busy(self, busy):
        for widget in (self.url_entry, self.folder_entry, self.browse_button, self.paste_button,
                       self.proxy_entry, self.cookie_entry, self.cookie_button, self.start_button):
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def start_download(self):
        if self.process is not None or self.closing:
            return
        try:
            url = normalize_url(self.url_var.get())
            proxy = validate_proxy(self.proxy_var.get())
            if not self.folder_var.get().strip():
                raise InputError("missing_folder")
            cookies = self.cookie_var.get().strip()
            if cookies and not Path(cookies).is_file():
                raise InputError("missing_cookies")
            self.job_dir = tempfile.TemporaryDirectory(prefix="xvd-job-")
            scratch = Path(self.job_dir.name)
            request = {"url": url, "proxy": proxy, "folder": self.folder_var.get().strip(), "cookies": cookies,
                       "language": self.language}
            request_path = scratch / "request.json"
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            self.process = subprocess.Popen(worker_command(request_path, scratch / "events.jsonl"),
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (ValueError, OSError) as exc:
            if self.job_dir:
                self.job_dir.cleanup()
                self.job_dir = None
            self.set_status("status_invalid")
            self.set_detail(exc.code if isinstance(exc, InputError) else "start_error")
            return
        self.remember()
        self.event_offset = 0
        self.final_event = None
        self.cancelled = False
        self.last_files = []
        self.retry = False
        self.start_button.configure(text=self.t("start"))
        self.set_busy(True)
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(12)
        self.percent_var.set("")
        self.set_status("connecting")
        self.set_detail("connecting_detail")
        self.poll_id = self.root.after(100, self.poll)

    def consume(self, event):
        kind = event.get("type")
        if kind in {"error", "complete"}:
            self.final_event = event
        elif self.cancelled:
            return
        elif kind in {"status", "notice", "processing"}:
            key = event.get("message_key") or {"status": "extracting", "notice": "notice", "processing": "processing_detail"}[kind]
            self.set_detail(key if key in TEXT[self.language] else "processing_detail")
            if kind == "processing":
                self.set_status("processing")
                self.progress.stop()
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
                self.percent_var.set("")
        elif kind == "progress":
            self.set_status("downloading")
            percent = event.get("percent")
            if percent is not None:
                self.progress.stop()
                self.progress.configure(mode="determinate", value=percent)
                self.percent_var.set(f"{percent:.0f}%")
            parts = [human_bytes(event.get("downloaded"))]
            if event.get("total"):
                parts[0] += " / " + human_bytes(event["total"])
            if event.get("speed"):
                parts.append(human_bytes(event["speed"]) + "/s")
            if event.get("eta") is not None:
                parts.append(self.t("eta", seconds=int(event["eta"])))
            if event.get("index"):
                parts.insert(0, self.t("video_index", index=event["index"]))
            self.detail_var.set("  ·  ".join(parts))
        elif kind == "video":
            self.detail_var.set(str(event.get("title") or self.t("video")))
        if kind not in {"error", "complete"}:
            self.last_display_event = event

    def read_events(self):
        events = Path(self.job_dir.name) / "events.jsonl"
        try:
            with events.open("rb") as stream:
                stream.seek(self.event_offset)
                for line in stream:
                    if not line.endswith(b"\n"):
                        break
                    self.event_offset += len(line)
                    try:
                        self.consume(json.loads(line.decode("utf-8")))
                    except (ValueError, TypeError, KeyError):
                        continue
        except FileNotFoundError:
            pass

    def poll(self):
        self.poll_id = None
        if self.process is None:
            return
        self.read_events()
        code = self.process.poll()
        if code is None or (self.stop_thread and self.stop_thread.is_alive()):
            self.poll_id = self.root.after(120, self.poll)
            return
        # Exit observed: the worker cannot append anything after this final drain.
        self.read_events()
        self.finish(code)

    def finish(self, code):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.percent_var.set("")
        self.set_busy(False)
        event = self.final_event or {}
        files = event.get("files", [])
        if self.cancelled:
            self.set_status("status_cancelled")
            self.set_detail("cancelled_detail")
        elif code == 0 and event.get("type") == "complete" and files and all(
                Path(p).is_file() and Path(p).stat().st_size > 0 for p in files):
            self.last_files = files
            self.set_status("status_complete", count=len(files))
            self.set_detail("saved_to", folder=str(Path(files[0]).parent))
            self.progress.configure(value=100)
            self.percent_var.set("100%")
        else:
            self.set_status("status_failed")
            key = event.get("message_key", "interrupted")
            self.set_detail(key if key in TEXT[self.language] else "interrupted")
            self.retry = True
            self.start_button.configure(text=self.t("retry"))
        self.process = None
        if self.job_dir:
            self.job_dir.cleanup()
            self.job_dir = None
        self.cookie_var.set("")
        if self.closing:
            self.root.destroy()

    def cancel_download(self):
        if self.process is None or self.cancelled:
            return
        self.cancelled = True
        self.cancel_button.configure(state="disabled")
        self.set_status("cancelling")
        self.set_detail("cancelling_detail")
        self.stop_thread = threading.Thread(target=stop_process_tree, args=(self.process,), daemon=True)
        self.stop_thread.start()

    def open_folder(self):
        folder = Path(self.last_files[0]).parent if self.last_files else Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except OSError:
            self.set_status("open_error")
            self.set_detail("open_error_detail")

    def help(self):
        messagebox.showinfo(self.t("help"), self.t("help_body"), parent=self.root)

    def close(self):
        self.remember()
        if self.process is not None:
            self.closing = True
            self.cancel_download()
        else:
            if self.poll_id:
                self.root.after_cancel(self.poll_id)
            self.root.destroy()


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        from worker import worker_main
        return worker_main(sys.argv[2], sys.argv[3])
    if len(sys.argv) == 3 and sys.argv[1] == "--diagnose":
        from worker import ffmpeg_path
        from yt_dlp.version import __version__
        binary = ffmpeg_path()
        probe = subprocess.run([binary, "-version"], capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, check=True)
        root = tk.Tk()
        root.withdraw()
        languages = {}
        with tempfile.TemporaryDirectory(prefix="xvd-diagnose-") as temp:
            ui = App(root, Path(temp) / "settings.json")
            initial_language = ui.language
            for language in LANGUAGE_NAMES:
                ui.set_language(language)
                root.update_idletasks()
                languages[language] = {"title": root.title(), "download": ui.start_button["text"],
                                       "font": ui.fonts["body"].actual("family")}
        root.destroy()
        Path(sys.argv[2]).write_text(json.dumps({"app": APP_VERSION, "yt_dlp": __version__,
            "ffmpeg": probe.stdout.splitlines()[0], "tk": tk.TkVersion,
            "default_language": initial_language, "languages": languages,
            "frozen": bool(getattr(sys, "frozen", False))},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Local.XVideoDownloader.1")
        except (OSError, AttributeError):
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
