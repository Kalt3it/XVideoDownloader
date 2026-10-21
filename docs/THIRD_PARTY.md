# Third-party build information

The application uses these independently maintained components:

| Component | Upstream | Distribution information |
| --- | --- | --- |
| Python 3.13 | https://www.python.org/ | Runtime license in `licenses/Python-LICENSE.txt` |
| Tcl/Tk 8.6 | https://www.tcl-lang.org/ | License in `licenses/Tcl-Tk-license.terms.txt` |
| yt-dlp | https://github.com/yt-dlp/yt-dlp | Package version pinned in `uv.lock`; notices in `THIRD-PARTY-NOTICES.txt` |
| imageio-ffmpeg 0.6.0 | https://github.com/imageio/imageio-ffmpeg | Supplies the Windows FFmpeg executable; BSD license applies to the Python wrapper |
| FFmpeg 7.1 | https://www.ffmpeg.org/ | Bundled binary identifies as `7.1-essentials_build-www.gyan.dev`, GPLv3 build |
| PyInstaller | https://pyinstaller.org/ | Build tool with its documented bootloader distribution exception |

FFmpeg references:

- FFmpeg 7.1 source archive: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz
- FFmpeg n7.1 source tree: https://github.com/FFmpeg/FFmpeg/tree/n7.1
- Windows binary supplier and build information: https://www.gyan.dev/ffmpeg/builds/
- FFmpeg GPLv3 text is included in `licenses/FFmpeg-GPL-3.0.txt`.

`imageio-ffmpeg`'s wrapper license does not replace the FFmpeg binary's license. Runtime dependency notices are collected from installed distribution metadata during the build; the exact Python dependency versions and wheel hashes are recorded in `uv.lock`.

The app source is included separately in the source ZIP and repository. No project-wide source license has been selected by the owner. Third-party licenses remain applicable to their respective components.
