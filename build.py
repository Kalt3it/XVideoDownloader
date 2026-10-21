"""Reproducible Windows single-file build using the local virtual environment."""
import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw
from core import APP_VERSION

ROOT = Path(__file__).resolve().parent


def main():
    assets = ROOT / "build" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    icon = Image.new("RGBA", (256, 256), "#152033")
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((8, 8, 248, 248), radius=52, fill="#152033")
    draw.line([(65, 55), (175, 190)], fill="white", width=22)
    draw.line([(177, 55), (65, 190)], fill="white", width=11)
    draw.rounded_rectangle((152, 148, 240, 238), radius=22, fill="#2563eb")
    draw.line([(196, 164), (196, 210)], fill="white", width=10)
    draw.line([(178, 195), (196, 213), (214, 195)], fill="white", width=9)
    icon_path = assets / "app.ico"
    icon.save(icon_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    ffmpeg = assets / "ffmpeg.exe"
    shutil.copyfile(imageio_ffmpeg.get_ffmpeg_exe(), ffmpeg)
    notices = [f"X Video Downloader {APP_VERSION} — bundled third-party notices\n",
               "FFmpeg 7.1 binary supplied by imageio-ffmpeg (GPL build).\n",
               "FFmpeg source: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz\n",
               "Binary wrapper supplier: https://github.com/imageio/imageio-ffmpeg\n",
               "Windows binary build supplier: https://www.gyan.dev/ffmpeg/builds/\n",
               "FFmpeg configuration and build license: run included --diagnose or ffmpeg -version.\n",
               "Python license: https://docs.python.org/3/license.html\n",
               "Tcl/Tk license: https://www.tcl-lang.org/software/tcltk/license.html\n\n"]
    for name in ("yt-dlp", "imageio-ffmpeg", "certifi", "requests", "urllib3", "idna", "charset-normalizer",
                 "brotli", "mutagen", "pycryptodomex", "websockets", "yt-dlp-ejs"):
        dist = importlib.metadata.distribution(name)
        notices.append(f"\n{'=' * 60}\n{name} {dist.version}\n")
        for file in dist.files or []:
            if any(word in file.name.lower() for word in ("license", "copying", "notice")):
                path = Path(dist.locate_file(file))
                if path.is_file() and path.suffix.lower() not in {".py", ".pyc"}:
                    notices.append(path.read_text(encoding="utf-8", errors="replace") + "\n")
    for license_path in sorted((ROOT / "licenses").glob("*.txt")):
        notices.append(f"\n{'=' * 60}\n{license_path.name}\n")
        notices.append(license_path.read_text(encoding="utf-8") + "\n")
    notices_path = ROOT / "THIRD-PARTY-NOTICES.txt"
    notices_path.write_text("\n".join(notices), encoding="utf-8")
    release = ROOT / "dist" / APP_VERSION
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--distpath", str(release),
           "--name", "X视频下载器", "--icon", str(icon_path),
           "--add-binary", f"{ffmpeg};bin", "--add-data", f"{notices_path};.", "--add-data", f"{icon_path};.",
           "--collect-all", "yt_dlp", "--collect-data", "certifi",
           "--exclude-module", "PIL", "--exclude-module", "unittest", "--exclude-module", "pytest",
           "--exclude-module", "numpy", "--exclude-module", "imageio_ffmpeg",
           str(ROOT / "app.py")]
    subprocess.run(cmd, cwd=ROOT, check=True)
    shutil.copyfile(ROOT / "README.md", release / "使用说明.txt")
    shutil.copyfile(notices_path, release / notices_path.name)
    print(f"Built: {release / 'X视频下载器.exe'}")


if __name__ == "__main__":
    main()
