import importlib.util
import json
import string
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

i18n = __import__("i18n") if importlib.util.find_spec("i18n") else None


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(i18n, "Four-language interface has not been implemented")

    def test_all_five_catalogs_have_complete_matching_format_fields(self):
        self.assertEqual(set(i18n.TEXT), {"zh", "zh_Hant", "ja", "ko", "en"})
        baseline = i18n.TEXT["en"]
        for lang, entries in i18n.TEXT.items():
            self.assertEqual(set(entries), set(baseline), lang)
            for key, text in entries.items():
                self.assertTrue(text.strip(), (lang, key))
                fields = lambda value: {field for _, field, _, _ in string.Formatter().parse(value) if field}
                self.assertEqual(fields(text), fields(baseline[key]), (lang, key))

    def test_detects_supported_system_locales_and_falls_back_to_english(self):
        for raw, expected in (("zh_CN", "zh"), ("zh-TW", "zh_Hant"), ("zh_Hant", "zh_Hant"),
                              ("zh-HK", "zh_Hant"), ("zh-Hant-HK", "zh_Hant"), ("ja_JP", "ja"),
                              ("ko-KR", "ko"), ("en_GB", "en"), ("fr_FR", "en"), (None, "en")):
            self.assertEqual(i18n.normalize_language(raw), expected)

    def test_renders_translated_errors_and_dynamic_counts(self):
        from core import friendly_error
        self.assertEqual(i18n.translate("en", "start"), "Download")
        self.assertIn("2", i18n.translate("ja", "status_complete", count=2))
        self.assertIn("네트워크", friendly_error("connection timeout", "ko"))
        self.assertIn("network", friendly_error("connection timeout", "en").lower())

    def test_remembers_language_and_recovers_unknown_language(self):
        from core import load_settings, save_settings
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            save_settings(path, {"folder": temp, "proxy": "", "language": "ja"})
            self.assertEqual(load_settings(path)["language"], "ja")
            path.write_text(json.dumps({"language": "unknown"}), encoding="utf-8")
            self.assertEqual(load_settings(path)["language"], "en")
            for invalid in (["ja"], {"code": "ko"}, 12, None):
                path.write_text(json.dumps({"language": invalid}), encoding="utf-8")
                self.assertEqual(load_settings(path)["language"], "en")

    def test_fresh_and_legacy_settings_default_to_english_but_keep_explicit_choices(self):
        from core import load_settings, save_settings
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            self.assertEqual(load_settings(path)["language"], "en")
            path.write_text(json.dumps({"folder": temp, "proxy": ""}), encoding="utf-8")
            self.assertEqual(load_settings(path)["language"], "en")
            save_settings(path, {"folder": temp, "language": "zh_Hant"})
            self.assertEqual(load_settings(path)["language"], "zh_Hant")
            self.assertEqual(load_settings(path)["folder"], temp)

    def test_traditional_chinese_ui_help_and_errors_are_localized(self):
        self.assertEqual(i18n.LANGUAGE_NAMES["zh_Hant"], "繁體中文")
        self.assertEqual(i18n.translate("zh_Hant", "start"), "開始下載")
        self.assertIn("網路", i18n.translate("zh_Hant", "network_error"))
        self.assertIn("繁體中文", i18n.translate("zh_Hant", "help_body"))


if __name__ == "__main__":
    unittest.main()
