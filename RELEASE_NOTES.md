# iTEST Exam Helper v1.0.0

- Windows 10/11 x64 installer, including Python, desktop dependencies, FFmpeg and the English speech model.
- Single-window desktop interface with settings, paper selection, progress and logs.
- Listening multiple-choice workflow; review answers in Edge before optional submission.
- Per-user settings and cache under `%LOCALAPPDATA%\iTEST-Exam-Helper`.
- No developer account, password, API key, recordings, exam pages or cache included.

Download `iTEST-Exam-Helper-1.0.0-windows-x64-setup.exe`, install, then launch iTEST.
Microsoft Edge and WebView2 are required. The installer checks WebView2 and offers
to download its Microsoft bootstrapper when missing. First login requires internet
access to obtain the Edge driver. Enter your own iTEST credentials and API key in Settings.
The API provider may charge for usage. Current support is limited to listening
multiple-choice papers; generated answers require review.

The installer is not code-signed. SHA256SUMS.txt provides the installer checksum.
Uninstall removes program files and retains your local settings and cache.
