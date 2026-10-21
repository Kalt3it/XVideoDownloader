"""Input validation and user preferences, independent of the desktop UI."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from i18n import DEFAULT_LANGUAGE, LANGUAGE_NAMES, translate

APP_NAME = "XVideoDownloader"
APP_VERSION = "1.1.1"


class InputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(translate(DEFAULT_LANGUAGE, code))


def normalize_url(text: str) -> str:
    value = text.strip()
    if not value or any(c.isspace() for c in value):
        raise InputError("invalid_link")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise InputError("invalid_url_format") from None
    if (parts.scheme not in {"https", "http"} or parts.username or parts.password
            or port is not None or (parts.hostname or "").lower() not in {
                "x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com",
            }):
        raise InputError("unsupported_host")
    path = parts.path.rstrip("/")
    if not re.fullmatch(r"/(?:[A-Za-z0-9_]{1,50}|i/web)/status/[0-9]+(?:/video/[1-9][0-9]*)?", path):
        raise InputError("invalid_post")
    return "https://x.com" + path


def validate_proxy(text: str) -> str:
    value = text.strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise InputError("proxy_port") from None
    if (parts.scheme not in {"http", "https", "socks5", "socks5h"} or not parts.hostname
            or not port or parts.username or parts.password or parts.path not in {"", "/"}
            or parts.query or parts.fragment or any(c.isspace() for c in value)):
        raise InputError("proxy_format")
    return value


def default_folder() -> str:
    return str(Path.home() / "Downloads" / "X Videos")


def settings_file() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME / "settings.json"


def load_settings(path: Path) -> dict:
    defaults = {"folder": default_folder(), "proxy": "", "language": DEFAULT_LANGUAGE}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if isinstance(data.get("language"), str) and data["language"] in LANGUAGE_NAMES:
                defaults["language"] = data["language"]
            if isinstance(data.get("folder"), str) and data["folder"].strip():
                defaults["folder"] = data["folder"]
            if isinstance(data.get("proxy"), str):
                defaults["proxy"] = validate_proxy(data["proxy"])
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def save_settings(path: Path, settings: dict) -> None:
    clean = {"folder": str(settings.get("folder") or default_folder()),
             "proxy": validate_proxy(str(settings.get("proxy", ""))),
             "language": settings.get("language") if isinstance(settings.get("language"), str)
             and settings["language"] in LANGUAGE_NAMES else DEFAULT_LANGUAGE}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace keeps interrupted writes from damaging existing preferences.
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def friendly_error_key(message: str) -> str:
    lower = message.lower()
    if any(s in lower for s in ("429", "rate limit", "too many requests")):
        return "rate_limit"
    if any(s in lower for s in ("login", "log in", "sign in", "authentication", "protected", "age-restricted", "nsfw")):
        return "login_required"
    if any(s in lower for s in ("no video", "does not contain", "no formats", "empty playlist")):
        return "no_video"
    if any(s in lower for s in ("no space", "disk full", "errno 28", "磁盘空间")):
        return "disk_full"
    if any(s in lower for s in ("permission", "access is denied", "errno 13", "拒绝访问")):
        return "permission_error"
    if any(s in lower for s in ("timed out", "timeout", "connection", "resolve", "proxy", "network", "ssl", "certificate")):
        return "network_error"
    if any(s in lower for s in ("404", "not found", "unavailable", "deleted")):
        return "unavailable"
    if "cookies" in lower or "netscape" in lower:
        return "cookies_invalid"
    if "403" in lower or "forbidden" in lower:
        return "forbidden"
    # Never echo arbitrary service messages, signed media URLs or credentials.
    return "download_error"


def friendly_error(message: str, language: str = DEFAULT_LANGUAGE) -> str:
    return translate(language, friendly_error_key(message))
