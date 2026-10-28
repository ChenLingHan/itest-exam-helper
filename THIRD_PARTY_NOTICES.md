# Third-party components

This application is derived from https://github.com/YDHusky/itest and is
distributed under the GNU AGPL v3; see LICENSE. This is an independent project.
The iTEST name and logo belong to their respective owners; see assets/README.md.

The Windows distribution includes Python (PSF License), pywebview (BSD),
pythonnet (MIT), Selenium (Apache-2.0), OpenAI Python SDK (Apache-2.0),
Vosk (Apache-2.0), requests (Apache-2.0), PyYAML (MIT), parsel (BSD),
and their dependencies. Installed package license texts are included under
`_internal/third-party-licenses` in the distribution.

The English speech model is vosk-model-small-en-us-0.15 (Apache-2.0):
https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip

FFmpeg 7.1.1 essentials build is supplied by Gyan, with GPL v3 enabled.
Build information and dependency/source links:
https://www.gyan.dev/ffmpeg/builds/
FFmpeg source for this version:
https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz
License: https://www.gnu.org/licenses/gpl-3.0.html
The complete FFmpeg build configuration can be inspected using
`_internal/lib/ffmpeg.exe -version`.

Microsoft Edge and WebView2 are Microsoft components installed separately on
Windows. Selenium Manager downloads a compatible Edge driver on first use.
