"""Optional public-site verification; saves only non-sensitive results."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import friendly_error
from worker import run_download

reports = Path(__file__).resolve().parents[1] / "reports"
reports.mkdir(exist_ok=True)
url = sys.argv[1] if len(sys.argv) > 1 else "https://x.com/captainamerica/status/719944021058060289"
try:
    files = run_download({"url": url, "folder": str(reports / "live-download")}, lambda e: print(e.get("type"), flush=True))
    result = {"ok": True, "url": url, "files": files}
except Exception as exc:
    result = {"ok": False, "url": url, "error_type": type(exc).__name__, "error": friendly_error(str(exc))}
(reports / "live-source-test.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True))
