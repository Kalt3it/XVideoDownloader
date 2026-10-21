"""Verify the shipped EXE's diagnostics and isolated downloader on a public post."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import APP_VERSION
EXE = ROOT / "dist" / APP_VERSION / "X视频下载器.exe"
REPORTS = ROOT / "reports" / "打包验证 空格" / APP_VERSION
REPORTS.mkdir(parents=True, exist_ok=True)


def main():
    diagnose = REPORTS / "diagnose.json"
    subprocess.run([str(EXE), "--diagnose", str(diagnose)], check=True, timeout=40)
    request = REPORTS / "request.json"
    events = REPORTS / "events.jsonl"
    request.write_text(json.dumps({"url": "https://x.com/captainamerica/status/719944021058060289",
                                  "folder": str(REPORTS / "视频输出"), "language": "en"}, ensure_ascii=False), encoding="utf-8")
    started = time.monotonic()
    process = subprocess.run([str(EXE), "--worker", str(request), str(events)], timeout=150, check=False)
    messages = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    result = messages[-1] if messages else {}
    ok = process.returncode == 0 and result.get("type") == "complete" and all(
        Path(p).is_file() and Path(p).stat().st_size > 0 for p in result.get("files", [])) and bool(result.get("files"))
    from i18n import LANGUAGE_NAMES, translate
    language_checks = {}
    for language in LANGUAGE_NAMES:
        test_request = REPORTS / f"invalid-{language}.json"
        test_events = REPORTS / f"invalid-{language}.jsonl"
        test_request.write_text(json.dumps({"url": "https://example.com/invalid", "folder": str(REPORTS),
                                           "language": language}), encoding="utf-8")
        failed = subprocess.run([str(EXE), "--worker", str(test_request), str(test_events)], timeout=40)
        event = json.loads(test_events.read_text(encoding="utf-8").splitlines()[-1])
        language_checks[language] = failed.returncode == 1 and event.get("message_key") == "unsupported_host" and event.get("message") == translate(language, "unsupported_host")
    diagnostics = json.loads(diagnose.read_text(encoding="utf-8"))
    ok = ok and all(language_checks.values()) and diagnostics.get("default_language") == "en"
    report = {"ok": ok, "exit_code": process.returncode, "seconds": round(time.monotonic() - started, 2),
              "worker_language_checks": language_checks,
              "diagnostics": diagnostics, "result": result,
              "progress_events": sum(m["type"] == "progress" for m in messages)}
    (ROOT / "reports" / "packaged-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
