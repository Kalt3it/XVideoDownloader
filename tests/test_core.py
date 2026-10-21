import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

core = __import__("core") if importlib.util.find_spec("core") else None


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(core, "Download core has not been implemented")

    def test_normalizes_supported_hosts_and_removes_share_tracking(self):
        cases = {
            " https://x.com/person/status/123456?s=20 ": "https://x.com/person/status/123456",
            "https://twitter.com/person/status/123456/video/2": "https://x.com/person/status/123456/video/2",
            "https://mobile.twitter.com/person/status/123456": "https://x.com/person/status/123456",
            "https://www.x.com/i/status/123456#fragment": "https://x.com/i/status/123456",
            "https://twitter.com/i/web/status/123456": "https://x.com/i/web/status/123456",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(core.normalize_url(raw), expected)

    def test_rejects_non_posts_lookalikes_credentials_and_unsupported_paths(self):
        for value in ("", "https://x.com/name", "https://x.com.evil.test/u/status/123",
                      "https://x.com@evil.test/u/status/123", "file:///x.com/u/status/123",
                      "https://user:secret@x.com/u/status/123", "https://x.com:8080/u/status/123",
                      "https://x.com/u/status/123/extra", "https://x.com/u/status/nope",
                      "https://x.com/u/status/123\nhttps://x.com/u/status/456"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    core.normalize_url(value)

    def test_proxy_allows_local_http_and_socks_but_rejects_credentials(self):
        self.assertEqual(core.validate_proxy("  http://127.0.0.1:7890  "), "http://127.0.0.1:7890")
        self.assertEqual(core.validate_proxy("socks5://localhost:1080"), "socks5://localhost:1080")
        self.assertEqual(core.validate_proxy(""), "")
        for value in ("http://u:secret@host:8080", "file:///tmp", "http://host/path", "127.0.0.1:7890"):
            with self.assertRaises(ValueError):
                core.validate_proxy(value)

    def test_settings_roundtrip_in_chinese_path_and_corrupt_file_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "中文 设置" / "settings.json"
            core.save_settings(path, {"folder": str(Path(tmp) / "视频"), "proxy": "http://127.0.0.1:7890"})
            self.assertEqual(core.load_settings(path)["folder"], str(Path(tmp) / "视频"))
            path.write_text("{broken", encoding="utf-8")
            self.assertTrue(core.load_settings(path)["folder"])
            path.write_text('["bad shape"]', encoding="utf-8")
            self.assertTrue(core.load_settings(path)["folder"])

    def test_does_not_persist_cookies_or_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            core.save_settings(path, {"folder": tmp, "proxy": "", "cookies": "private.txt", "secret": "private"})
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(saved), {"folder", "proxy", "language"})

    def test_friendly_errors_explain_recoverable_failures(self):
        for error, word in (("HTTP Error 429", "频繁"), ("timed out", "网络"),
                            ("No video could be found", "视频"), ("Login required", "登录"),
                            ("No space left on device", "空间")):
            self.assertIn(word, core.friendly_error(error, "zh"))


if __name__ == "__main__":
    unittest.main()
