# X Video Downloader

A flat, multilingual Windows desktop app for saving videos from X / Twitter post links.

**Version 1.1.1 · Windows 10/11 x64 · English / 简体中文 / 繁體中文 / 日本語 / 한국어**

## Download

Open this repository's **Releases** page and download the Windows x64 ZIP. Extract it and run `XVideoDownloader.exe`. The standalone versioned EXE also runs directly. Python and FFmpeg are included; no separate runtime installation is required.

GitHub's automatically generated **Source code** archives contain source, not a ready-to-run Windows app.

1. Copy a post link from X / Twitter's share menu.
2. Paste it into the app and choose a save folder.
3. Click **Download**, then **Open folder** when finished.

Features include best available video quality, multiple videos per post, progress, cancellation, retry, a flat scrollable interface and instant language switching. First launch defaults to English; explicit language and folder choices are remembered.

Your network must be able to access X. A proxy URL and manually selected Netscape-format cookies file are optional. The app does not automatically read browser sign-in data. Deleted or restricted posts and changes to X may prevent downloads.

See [building and testing](docs/BUILDING.md) and the [changelog](CHANGELOG.md).

## 中文使用说明

Windows 10 / 11，64 位。从 Releases 下载 ZIP，解压后双击 `XVideoDownloader.exe` 即可打开；单独的版本号 EXE 也可以直接运行。不需要安装 Python 或 FFmpeg。

界面语言：English / 简体中文 / 繁體中文 / 日本語 / 한국어。首次启动默认英语，不再跟随系统语言。顶部菜单即时切换并记住选择；升级保留已保存的语言和路径。按钮、状态、错误提示、帮助及应用内文件选择标题均支持五种语言。系统原生文件对话框中的系统按钮由 Windows 决定。

English: Double-click the EXE; no Python installation required. Paste an X/Twitter post link, choose a folder and click Download. Switch languages in the top-right menu. Network access to X is required; a proxy and your exported Netscape cookies file are optional. The app does not automatically read browser sign-in data.

繁體中文：首次啟動預設為 English，可在頂端選單切換為繁體中文並記住選擇。貼上 X / Twitter 貼文連結，選擇儲存資料夾後按下「開始下載」。不需要安裝 Python；可使用自己的代理伺服器與 Netscape 格式 Cookies 檔案。軟體不會自動讀取瀏覽器的登入資訊。

日本語：EXE をダブルクリックして起動します。Python のインストールは不要です。投稿リンクを貼り付け、保存先を選んでダウンロードしてください。右上で言語を切り替えられます。X に接続可能なネットワークが必要です。プロキシとご自身の Netscape 形式 Cookies は任意です。ブラウザーのログイン情報は自動取得しません。

한국어: EXE를 더블클릭하면 실행되며 Python 설치는 필요 없습니다. 게시물 링크를 붙여넣고 저장 폴더를 선택한 뒤 다운로드하세요. 오른쪽 위에서 언어를 변경할 수 있습니다. X에 접근 가능한 네트워크가 필요하며 프록시와 직접 내보낸 Netscape Cookies 파일은 선택 사항입니다. 브라우저 로그인 정보를 자동으로 읽지 않습니다.

## 使用

1. 在 X / Twitter 的分享菜单复制一条帖子链接。
2. 点击「粘贴链接」，选择保存文件夹。
3. 点击「开始下载」。软件使用可用的最高画质，优先保存 MP4；同一帖子含多个视频时一并下载。
4. 完成后点击「打开文件夹」。保存路径会自动记住。

窗口支持鼠标滚轮和右侧滚动条；窗口较小或展开网络选项时，可以向下滚动查看全部内容，也可使用 Page Up / Page Down。

1.0.2 改为细窄、无箭头的扁平滚动条，支持拖动和点击定位；内容完整显示时滑块自动隐藏。按钮、输入框和进度条使用统一的扁平样式。

取消后可以再次点击开始下载。完整文件会保留，不覆盖已有视频；下载片段在可用时继续。

## 网络与登录

软件需要当前网络可以访问 X。若浏览器能打开 X，但下载连接失败，请展开「网络与登录选项」，填写自己的代理地址，例如 http://127.0.0.1:7890（端口以你实际使用的代理软件为准）。留空使用系统网络。软件不提供代理服务。

部分帖子需要登录。此时可手动选择你自己导出的 Netscape 格式 cookies.txt 文件。软件不自动读取浏览器登录信息；只在本次任务使用临时副本，任务结束或取消后清理副本，不保存 Cookies 路径。关闭窗口也会停止当前下载。

只支持具体帖子的 x.com / twitter.com 链接，不支持整个用户主页、私信、直播和其他网站。图片不下载。

帖子删除、账号访问限制或 X 接口变化可能导致下载失败。出现失败时，界面会提示网络、登录或链接问题；可以修正后重试。下载文件名使用账号和视频 ID，避免长标题和无效字符。

## 文件与组件

配置文件：%APPDATA%\XVideoDownloader\settings.json，仅保存界面语言、输出文件夹和不含账号密码的代理地址。升级会保留已有保存位置。

内置 yt-dlp 与 FFmpeg；第三方许可见 [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt)、[licenses](licenses/) 和[第三方构建信息](docs/THIRD_PARTY.md)。源码目录包含实现、自动化测试和构建脚本。项目源码整体许可证尚未由所有者选择，第三方组件继续使用各自的许可证。

源码仓库只包含代码、测试和说明。生成的 EXE、开发环境、本地报告与认证文件被排除；可运行程序通过 Releases 分发。

开发环境：Python 3.13。优先运行 uv sync --locked，再运行 .venv\Scripts\python.exe -m unittest discover -s tests -v；构建运行 .venv\Scripts\python.exe build.py。若本机 uv 的脚本启动器生成失败，可用虚拟环境内的 pip 安装 pyproject.toml 声明的依赖及 pyinstaller、pillow。

诊断：`XVideoDownloader.exe --diagnose <诊断JSON的完整路径>`，检查内置 Tk、下载组件及 FFmpeg。
