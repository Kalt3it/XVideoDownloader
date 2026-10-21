import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

app = __import__("app") if importlib.util.find_spec("app") else None


class AppTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(app, "Desktop application has not been implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        # Layout tests need mapped widgets, but never a visible or active window.
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.0)
        if sys.platform == "win32":
            self.root.attributes("-disabled", True)
        self.root.withdraw()
        config = Path(self.temp.name) / "设置" / "settings.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"language": "zh"}), encoding="utf-8")
        self.ui = app.App(self.root, Path(self.temp.name) / "设置" / "settings.json")
        self.ui.folder_var.set(str(Path(self.temp.name) / "中文 输出"))

    def tearDown(self):
        if hasattr(self, "root"):
            if self.ui.poll_id:
                self.root.after_cancel(self.ui.poll_id)
            if self.ui.process and self.ui.process.poll() is None:
                self.ui.process.kill()
                self.ui.process.wait(timeout=5)
            if self.ui.job_dir:
                self.ui.job_dir.cleanup()
            self.root.destroy()
            self.temp.cleanup()

    def pump(self, predicate, timeout=10):
        end = time.monotonic() + timeout
        while not predicate() and time.monotonic() < end:
            self.root.update()
            time.sleep(0.02)
        self.assertTrue(predicate(), "Desktop flow did not finish within deadline")

    def test_invalid_url_displays_error_without_starting_worker(self):
        self.ui.url_var.set("https://example.com/video")
        self.ui.start_download()
        self.assertIsNone(self.ui.process)
        self.assertIn("帖子", self.ui.status_var.get())

    def test_language_switch_updates_existing_controls_and_persists(self):
        switch = getattr(self.ui, "set_language", None)
        self.assertTrue(callable(switch), "The UI needs live language switching")
        self.ui.url_var.set("https://x.com/example/status/123456")
        for language, label, title in (("en", "Download", "X Video Downloader"),
                                        ("zh_Hant", "開始下載", "X 影片下載器"),
                                        ("ja", "ダウンロード", "X 動画ダウンローダー"),
                                        ("ko", "다운로드", "X 동영상 다운로더"),
                                        ("zh", "开始下载", "X 视频下载器")):
            switch(language)
            self.root.update_idletasks()
            self.assertEqual(self.ui.start_button["text"], label)
            self.assertEqual(self.root.title(), title)
            self.assertEqual(self.ui.url_var.get(), "https://x.com/example/status/123456")
            saved = json.loads(self.ui.settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["language"], language)

    def test_language_change_retranslates_current_validation_error(self):
        switch = getattr(self.ui, "set_language", None)
        self.assertTrue(callable(switch), "The UI needs translated validation errors")
        self.ui.url_var.set("invalid")
        self.ui.start_download()
        switch("en")
        self.assertIn("Check", self.ui.status_var.get())
        self.assertIn("link", self.ui.detail_var.get().lower())

    def test_language_is_remembered_even_while_proxy_input_is_incomplete(self):
        self.ui.proxy_var.set("http://127.0.0.1:7890")
        self.ui.remember()
        self.ui.proxy_var.set("http://127.0.0.1:")
        self.ui.set_language("ja")
        saved = json.loads(self.ui.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["language"], "ja")
        self.assertEqual(saved["proxy"], "http://127.0.0.1:7890")

    def test_selecting_language_with_enter_does_not_start_a_download(self):
        self.root.deiconify()
        self.root.update()
        combo = getattr(self.ui, "language_combo", None)
        self.assertIsNotNone(combo)
        self.ui.handle_return(SimpleNamespace(widget=combo))
        self.root.update()
        self.assertIn("准备", self.ui.status_var.get())

    def test_all_languages_keep_advanced_controls_and_footer_accessible(self):
        self.root.deiconify()
        self.ui.toggle_advanced()
        self.root.geometry("740x500")
        for language in ("zh", "zh_Hant", "ja", "ko", "en"):
            self.ui.set_language(language)
            self.root.update()
            canvas = self.ui.scroll_canvas
            canvas.yview_moveto(1)
            self.root.update()
            for widget in (self.ui.cookie_button, self.ui.open_button, self.ui.help_button):
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     canvas.winfo_rootx() + canvas.winfo_width(), language)
            self.assertLessEqual(self.ui.help_button.winfo_rooty() + self.ui.help_button.winfo_height(),
                                 canvas.winfo_rooty() + canvas.winfo_height(), language)

    def test_switch_during_download_keeps_same_process_and_translates_worker_events(self):
        switch = getattr(self.ui, "set_language", None)
        self.assertTrue(callable(switch), "The UI needs live switching during an active job")
        self.ui.url_var.set("https://x.com/test/status/123456")
        with patch("app.worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]):
            self.ui.start_download()
        process = self.ui.process
        switch("en")
        self.assertIs(self.ui.process, process)
        self.assertEqual(str(self.ui.start_button["state"]), "disabled")
        self.ui.consume({"type": "status", "message_key": "extracting", "message": "旧语言"})
        self.assertIn("quality", self.ui.detail_var.get().lower())
        switch("ja")
        self.assertIn("画質", self.ui.detail_var.get())
        self.ui.cancel_download()
        self.pump(lambda: self.ui.process is None)

    def test_small_window_scrolls_to_footer_and_advanced_options(self):
        self.root.deiconify()
        self.ui.toggle_advanced()
        self.root.geometry("740x500")
        self.root.update()
        canvas = getattr(self.ui, "scroll_canvas", None)
        self.assertIsNotNone(canvas, "The interface needs a scrollable viewport")
        self.assertLess(canvas.yview()[1], 1.0)
        before = canvas.yview()[0]
        self.ui.url_entry.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(canvas.yview()[0], before)
        canvas.yview_moveto(1.0)
        self.root.update()
        footer = self.ui.help_button
        self.assertGreaterEqual(footer.winfo_rooty(), canvas.winfo_rooty())
        self.assertLessEqual(footer.winfo_rooty() + footer.winfo_height(),
                             canvas.winfo_rooty() + canvas.winfo_height())

    def test_flat_scrollbar_drag_and_track_click_move_the_page(self):
        self.root.deiconify()
        self.ui.toggle_advanced()
        self.root.geometry("740x500")
        self.root.update()
        bar = self.ui.scrollbar
        self.assertIsInstance(bar, tk.Canvas, "Use the flat drawn scrollbar instead of a classic native control")
        bounds = bar.bbox("thumb")
        self.assertIsNotNone(bounds)
        x = bar.winfo_width() // 2
        y = (bounds[1] + bounds[3]) // 2
        bar.event_generate("<ButtonPress-1>", x=x, y=y)
        bar.event_generate("<B1-Motion>", x=x, y=bar.winfo_height() - 12)
        bar.event_generate("<ButtonRelease-1>", x=x, y=bar.winfo_height() - 12)
        self.root.update()
        self.assertAlmostEqual(self.ui.scroll_canvas.yview()[1], 1.0, places=2)
        bar.event_generate("<ButtonPress-1>", x=x, y=10)
        bar.event_generate("<ButtonRelease-1>", x=x, y=10)
        self.root.update()
        self.assertAlmostEqual(self.ui.scroll_canvas.yview()[0], 0.0, places=2)

    def test_flat_scrollbar_hides_thumb_when_content_fits(self):
        self.root.deiconify()
        self.root.geometry("820x1000")
        self.root.update()
        bar = self.ui.scrollbar
        self.assertIsInstance(bar, tk.Canvas)
        self.assertFalse(bar.find_withtag("thumb"))
        self.ui.toggle_advanced()
        self.root.geometry("740x500")
        self.root.update()
        self.assertTrue(bar.find_withtag("thumb"))

    def test_valid_job_reports_real_worker_network_error_and_allows_retry(self):
        self.ui.url_var.set("https://x.com/test/status/123456")
        self.ui.proxy_var.set("http://127.0.0.1:1")
        self.ui.start_download()
        self.assertIsNotNone(self.ui.process)
        self.pump(lambda: self.ui.process is None, timeout=35)
        self.assertIn("失败", self.ui.status_var.get())
        self.assertEqual(str(self.ui.start_button["state"]), "normal")
        stored = json.loads(self.ui.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["folder"], self.ui.folder_var.get())
        self.assertIsNone(self.ui.job_dir)

    def test_cancel_stops_actual_process_and_removes_temporary_credentials(self):
        self.ui.url_var.set("https://x.com/test/status/123456")
        # A real long-running child stands in for an external request that stalls.
        with patch("app.worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]):
            self.ui.start_download()
        proc = self.ui.process
        job = Path(self.ui.job_dir.name)
        (job / "temporary-cookie.txt").write_text("private", encoding="utf-8")
        self.ui.cancel_download()
        self.pump(lambda: self.ui.process is None)
        self.assertIsNotNone(proc.poll())
        self.assertFalse(job.exists())
        self.assertIn("取消", self.ui.status_var.get())

    def test_completed_event_requires_real_output_and_enables_folder_button(self):
        self.ui.url_var.set("https://x.com/test/status/123456")
        output = Path(self.temp.name) / "完成.mp4"
        output.write_bytes(b"media")
        with patch("app.worker_command", return_value=[sys.executable, "-c", "pass"]):
            self.ui.start_download()
        Path(self.ui.job_dir.name, "events.jsonl").write_text(
            json.dumps({"type": "complete", "files": [str(output)]}) + "\n", encoding="utf-8")
        self.pump(lambda: self.ui.process is None)
        self.assertIn("完成", self.ui.status_var.get())
        self.assertEqual(self.ui.last_files, [str(output)])

    def test_missing_output_is_not_reported_as_success(self):
        self.ui.url_var.set("https://x.com/test/status/123456")
        with patch("app.worker_command", return_value=[sys.executable, "-c", "pass"]):
            self.ui.start_download()
        Path(self.ui.job_dir.name, "events.jsonl").write_text(
            json.dumps({"type": "complete", "files": [str(Path(self.temp.name) / "missing.mp4")]}) + "\n",
            encoding="utf-8")
        self.pump(lambda: self.ui.process is None)
        self.assertIn("失败", self.ui.status_var.get())

    def test_zero_byte_output_is_not_reported_as_success(self):
        self.ui.url_var.set("https://x.com/test/status/123456")
        output = Path(self.temp.name) / "empty.mp4"
        output.touch()
        with patch("app.worker_command", return_value=[sys.executable, "-c", "pass"]):
            self.ui.start_download()
        Path(self.ui.job_dir.name, "events.jsonl").write_text(
            json.dumps({"type": "complete", "files": [str(output)]}) + "\n", encoding="utf-8")
        self.pump(lambda: self.ui.process is None)
        self.assertIn("失败", self.ui.status_var.get())

    def test_drains_completion_written_between_read_and_exit_check(self):
        self.ui.url_var.set("https://x.com/test/status/123456")
        output = Path(self.temp.name) / "race.mp4"
        output.write_bytes(b"media")
        with patch("app.worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]):
            self.ui.start_download()
        original = self.ui.process
        original.kill()
        original.wait(timeout=5)
        events_path = Path(self.ui.job_dir.name) / "events.jsonl"
        class ExitAtPoll:
            def poll(_self):
                events_path.write_text(json.dumps({"type":"complete", "files":[str(output)]}) + "\n", encoding="utf-8")
                return 0
        self.ui.process = ExitAtPoll()
        self.root.after_cancel(self.ui.poll_id)
        self.ui.poll()
        self.assertIn("完成", self.ui.status_var.get())


if __name__ == "__main__":
    unittest.main()
