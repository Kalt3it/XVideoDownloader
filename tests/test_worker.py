import functools
import http.server
import importlib.util
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

worker = __import__("worker") if importlib.util.find_spec("worker") else None


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(worker, "Isolated download worker has not been implemented")

    def test_invalid_url_reports_error_event_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp) / "request.json"
            events = Path(tmp) / "events.jsonl"
            request.write_text(json.dumps({"url": "https://evil.test/a", "folder": tmp}), encoding="utf-8")
            self.assertEqual(worker.worker_main(str(request), str(events)), 1)
            messages = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(messages[-1]["type"], "error")
            self.assertFalse(any(m["type"] == "complete" for m in messages))

    def test_no_video_result_is_failure(self):
        from yt_dlp.extractor.twitter import TwitterIE
        events = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(TwitterIE, "_real_extract", return_value={
            "_type": "playlist", "id": "123456", "entries": [], "title": "No media",
        }):
            with self.assertRaises(ValueError):
                worker.run_download({"url": "https://x.com/test/status/123456", "folder": tmp}, events.append)

    def test_downloads_best_real_mp4_to_chinese_folder_and_preserves_existing_file(self):
        import imageio_ffmpeg
        from yt_dlp.extractor.twitter import TwitterIE
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            media = base / "media"
            media.mkdir()
            sample = media / "sample.mp4"
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i",
                            "color=c=blue:s=64x64:d=0.25", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            str(sample)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            handler = functools.partial(QuietHandler, directory=str(media))
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/sample.mp4"
                info = {"id": "123456", "title": "中文视频", "uploader_id": "tester", "formats": [
                    {"format_id": "low", "url": url, "ext": "mp4", "height": 32, "vcodec": "h264", "acodec": "none"},
                    {"format_id": "high", "url": url, "ext": "mp4", "height": 64, "vcodec": "h264", "acodec": "none"},
                ]}
                events = []
                request = {"url": "https://x.com/test/status/123456", "folder": str(base / "中文 输出"),
                           "proxy": "", "cookies": ""}
                with patch.object(TwitterIE, "_real_extract", return_value=info):
                    paths = worker.run_download(request, events.append)
                self.assertEqual(len(paths), 1)
                output = Path(paths[0])
                self.assertEqual(output.read_bytes(), sample.read_bytes())
                self.assertTrue(any(e["type"] == "progress" for e in events))
                self.assertTrue(any(e.get("height") == 64 for e in events if e["type"] == "video"))
                output.write_bytes(b"do-not-overwrite")
                with patch.object(TwitterIE, "_real_extract", return_value=info):
                    worker.run_download(request, events.append)
                self.assertEqual(output.read_bytes(), b"do-not-overwrite")
                output.write_bytes(b"")
                with patch.object(TwitterIE, "_real_extract", return_value=info):
                    with self.assertRaises(ValueError):
                        worker.run_download(request, events.append)

                # Legacy native Twitter videos redirect through TwitterAmplifyIE.
                from yt_dlp.extractor.twitter import TwitterAmplifyIE
                redirect = {"_type": "url", "url": "https://amp.twimg.com/v/0ba0c3c7-0af3-4c0a-bed5-7efd1ffa2951",
                            "ie_key": "TwitterAmplify"}
                info["id"] = "legacy-video"
                with patch.object(TwitterIE, "_real_extract", return_value=redirect), \
                     patch.object(TwitterAmplifyIE, "_real_extract", return_value=info):
                    legacy = worker.run_download(request, events.append)
                self.assertEqual(Path(legacy[0]).read_bytes(), sample.read_bytes())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
