"""Create a verified, allow-listed source folder and manual GitHub release assets."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import APP_VERSION

PUBLIC_FILES = [
    ".gitignore", ".gitattributes", ".editorconfig", "README.md", "CHANGELOG.md",
    "app.py", "core.py", "worker.py", "widgets.py", "i18n.py", "build.py",
    "pyproject.toml", "uv.lock", "THIRD-PARTY-NOTICES.txt",
    "docs/BUILDING.md", "docs/THIRD_PARTY.md",
    f"docs/releases/v{APP_VERSION}.md",
    "tools/live_check.py", "tools/packaged_check.py", "tools/prepare_github.py",
]
SECRET_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+"),
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def zip_files(target, items):
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, name in items:
            archive.write(path, name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity test failed")


def prepare(output):
    exe = ROOT / "dist" / APP_VERSION / "X视频下载器.exe"
    if not exe.is_file():
        raise FileNotFoundError("Build the release EXE first")
    files = sorted(set(PUBLIC_FILES + [p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("test_*.py")]
                       + [p.relative_to(ROOT).as_posix() for p in (ROOT / "licenses").glob("*.txt")]))
    if not (ROOT / "licenses" / "FFmpeg-GPL-3.0.txt").is_file():
        raise FileNotFoundError("Third-party license files are missing")
    for relative in files:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size >= 25 * 1024 * 1024:
            raise ValueError(f"Missing or oversized source file: {relative}")
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Review private information before packaging: {relative}")
    if len(files) > 100:
        raise ValueError("Split the browser upload into batches of at most 100 files")
    output.mkdir(parents=True, exist_ok=False)
    source = output / "SOURCE"
    assets = output / "RELEASE_ASSETS"
    assets.mkdir()
    for relative in files:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)

    base = f"XVideoDownloader-v{APP_VERSION}-windows-x64"
    standalone = assets / f"{base}.exe"
    shutil.copyfile(exe, standalone)
    source_zip = assets / f"x-video-downloader-v{APP_VERSION}-source.zip"
    zip_files(source_zip, [(source / name, f"x-video-downloader/{name}") for name in files])
    portable = assets / f"{base}.zip"
    portable_files = [(exe, "XVideoDownloader.exe"), (source / "README.md", "README.txt"),
                      (source / "THIRD-PARTY-NOTICES.txt", "THIRD-PARTY-NOTICES.txt"),
                      (source / "docs/THIRD_PARTY.md", "THIRD-PARTY-SOURCES.md")]
    portable_files += [(source / name, name) for name in files if name.startswith("licenses/")]
    zip_files(portable, portable_files)

    with zipfile.ZipFile(portable) as archive:
        if hashlib.sha256(archive.read("XVideoDownloader.exe")).hexdigest() != digest(exe):
            raise RuntimeError("Packaged EXE does not match the tested build")
    with zipfile.ZipFile(source_zip) as archive:
        for name in files:
            if hashlib.sha256(archive.read(f"x-video-downloader/{name}")).hexdigest() != digest(source / name):
                raise RuntimeError(f"Source ZIP content mismatch: {name}")
    if digest(standalone) != digest(exe):
        raise RuntimeError("Standalone release EXE changed while copying")

    checksum = assets / "SHA256SUMS.txt"
    checksum.write_text("".join(f"{digest(path)}  {path.name}\n" for path in (standalone, portable, source_zip)), encoding="utf-8")
    shutil.copyfile(source / f"docs/releases/v{APP_VERSION}.md", output / "release-notes.md")
    (output / "README-FIRST.txt").write_text(
        "SOURCE：只把这个文件夹里面的文件和子文件夹上传到仓库 Code。\n"
        "RELEASE_ASSETS：里面的四个文件全部上传到 Releases 的附件区。\n"
        "release-notes.md：复制正文作为版本发布说明。\n"
        "先上传源码，再创建版本发布并添加附件。\n"
        "本目录由本地脚本准备；没有登录、创建或修改任何 GitHub 仓库。\n", encoding="utf-8")
    manifest = {"version": APP_VERSION, "tag": f"v{APP_VERSION}", "source_file_count": len(files),
                "source_files": [{"path": name, "sha256": digest(source / name),
                                  "bytes": (source / name).stat().st_size} for name in files],
                "release_assets": [{"name": path.name, "sha256": digest(path), "bytes": path.stat().st_size}
                                   for path in sorted(assets.iterdir())],
                "checks": {"source_allowlist": True, "secret_and_private_path_scan": True,
                           "zip_integrity": True, "source_hashes": True, "exe_hash_match": True}}
    (output / "upload-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "source_files": len(files),
                      "source_bytes": sum((source / name).stat().st_size for name in files),
                      "assets": [p.name for p in sorted(assets.iterdir())], "checks": manifest["checks"]}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "github-upload" / f"v{APP_VERSION}")
    args = parser.parse_args()
    prepare(args.output.resolve())
