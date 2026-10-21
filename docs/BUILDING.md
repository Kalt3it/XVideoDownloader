# Building and testing

## Requirements

- Windows 10 or 11, x64.
- Python 3.13.
- uv, or pip with a virtual environment.
- Network access to the configured Python package index for dependency installation.

## Install locked dependencies

Run from the repository root in PowerShell:

```powershell
uv sync --locked
```

If uv's Windows script launcher fails on a particular machine, a pip fallback is available:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "yt-dlp[default]" imageio-ffmpeg pyinstaller pillow
```

The uv lockfile is the pinned dependency reference. The pip fallback resolves package versions at installation time.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use locally generated media and a local HTTP server. They do not need a live X account or browser cookies. Tk layout tests use transparent, undecorated windows with system input disabled; they do not show preview windows or force focus.

## Build a single EXE

```powershell
.\.venv\Scripts\python.exe build.py
```

The result is `dist/<version>/X视频下载器.exe`. FFmpeg is taken from the locked `imageio-ffmpeg` package. The build also embeds third-party license notices.

To prepare clean GitHub source and release assets:

```powershell
.\.venv\Scripts\python.exe tools/prepare_github.py
```

This creates a new `github-upload/v<version>/` directory. It refuses to overwrite an existing preparation directory; choose a fresh location with `--output` for subsequent runs.

## Diagnostics

```powershell
& ".\dist\<version>\X视频下载器.exe" --diagnose "$PWD\diagnose.json"
```

Hidden diagnostics check the bundled runtime, FFmpeg, default language, all language labels and available fonts. They do not start a visible preview or read browser credentials.

`tools/packaged_check.py` is an optional integration check that accesses one public X post and verifies localized worker errors. It writes local output under `reports/`, which is not part of the source repository. Run it only when live-site verification is wanted.
