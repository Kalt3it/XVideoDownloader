"""Isolated downloader. Events are local JSON lines, never console output."""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from core import InputError, friendly_error_key, normalize_url, validate_proxy
from i18n import DEFAULT_LANGUAGE, translate


def ffmpeg_path() -> str:
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_download(request: dict, emit) -> list[str]:
    from yt_dlp import YoutubeDL

    language = request.get("language", DEFAULT_LANGUAGE)
    def message_event(kind, key):
        emit({"type": kind, "message_key": key, "message": translate(language, key)})

    url = normalize_url(request.get("url", ""))
    proxy = validate_proxy(request.get("proxy", ""))
    folder_text = str(request.get("folder", "")).strip()
    if not folder_text:
        raise InputError("missing_folder")
    folder = Path(folder_text).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    # Detect permission/disk errors before making an expensive network request.
    with tempfile.TemporaryFile(dir=folder):
        pass
    outputs = []
    last_progress = [0.0]

    class Logger:
        def debug(self, message):
            pass

        def info(self, message):
            pass

        def warning(self, message):
            message_event("notice", "notice")

        def error(self, message):
            pass

    def progress(data):
        now = time.monotonic()
        if data["status"] == "downloading" and now - last_progress[0] < 0.15:
            return
        last_progress[0] = now
        if data["status"] == "finished":
            message_event("processing", "processing_detail")
            return
        if data["status"] != "downloading":
            return
        downloaded = data.get("downloaded_bytes") or 0
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        info = data.get("info_dict") or {}
        emit({"type": "progress", "downloaded": downloaded, "total": total,
              "percent": min(100.0, downloaded / total * 100) if total else None,
              "speed": data.get("speed"), "eta": data.get("eta"),
              "index": info.get("playlist_index"), "count": info.get("n_entries")})

    def collect(output):
        if output and Path(output).is_file() and Path(output).stat().st_size > 0 and output not in outputs:
            outputs.append(str(Path(output).resolve()))

    def announce(data):
        if data.get("status") == "started":
            info = data.get("info_dict") or {}
            emit({"type": "video", "title": str(info.get("title", ""))[:180],
                  "height": info.get("height"), "index": info.get("playlist_index")})

    options = {
        "quiet": True, "no_warnings": True, "noprogress": True, "logger": Logger(),
        "format": "bv*+ba/b", "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_path(),
        "outtmpl": str(folder / "%(uploader_id,channel_id|X)s_%(id)s.%(ext)s"),
        "windowsfilenames": True, "trim_file_name": 160,
        "overwrites": False, "continuedl": True,
        "socket_timeout": 20, "retries": 3, "fragment_retries": 3, "extractor_retries": 2,
        "concurrent_fragment_downloads": 3,
        "progress_hooks": [progress], "post_hooks": [collect], "postprocessor_hooks": [announce],
        "ignoreerrors": False, "noplaylist": False,
        "allowed_extractors": ["twitter", "twitter:amplify", "twitter:card"],
    }
    if proxy:
        options["proxy"] = proxy
    message_event("status", "extracting")
    # yt-dlp may update its cookie jar; use a per-job copy to protect the source.
    with tempfile.TemporaryDirectory(prefix="auth-", dir=request.get("_scratch_dir")) as private:
        cookies = request.get("cookies", "")
        if cookies:
            source = Path(cookies)
            if not source.is_file():
                raise InputError("missing_cookies")
            dest = Path(private) / "cookies.txt"
            shutil.copyfile(source, dest)
            options["cookiefile"] = str(dest)
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            # post_hooks see final paths, including already-downloaded files.
            if not info or not outputs:
                raise ValueError("No video could be found")
    return outputs


def worker_main(request_path: str, events_path: str) -> int:
    language = "en"
    with Path(events_path).open("w", encoding="utf-8", buffering=1) as stream:
        def emit(event):
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
        try:
            request = json.loads(Path(request_path).read_text(encoding="utf-8"))
            language = request.get("language", DEFAULT_LANGUAGE)
            request["_scratch_dir"] = str(Path(events_path).resolve().parent)
            paths = run_download(request, emit)
            emit({"type": "complete", "files": paths})
            return 0
        except Exception as exc:
            key = exc.code if isinstance(exc, InputError) else friendly_error_key(str(exc))
            emit({"type": "error", "message_key": key, "message": translate(language, key)})
            return 1
