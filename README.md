# iTEST Exam Helper

Windows 桌面版 iTEST 英语考试辅助工具，基于 [YDHusky/itest](https://github.com/YDHusky/itest) 改进，采用 AGPL-3.0 许可证。非 iTEST 官方产品。

官网：**https://chenlinghan.github.io/itest-exam-helper/**

## 下载安装

在 [Releases](https://github.com/ChenLingHan/itest-exam-helper/releases/tag/v1.2.2) 下载 `iTEST-Exam-Helper-1.2.2-windows-x64-setup.exe`，双击安装，完成后从桌面或开始菜单打开 **iTEST**。

- 支持 Windows 10/11 64 位（x64），无需安装 Python 或手动安装依赖。
- 内置英语离线语音模型及 FFmpeg。
- 请安装 Microsoft Edge；缺少 WebView2 时，安装程序会提示安装 Microsoft 官方组件，需要联网。
- 首次获取试卷时，Selenium Manager 会联网下载与 Edge 匹配的驱动。
- 安装包未进行代码签名。发布页附 SHA256SUMS.txt，可用于核对下载文件。

窗口默认置顶，Edge 打开时软件仍显示在其上方。可随时通过左下角“窗口置顶”开关取消；选择会自动保存，下次启动继续生效。

## 首次使用

1. 在“设置”的“运行环境”中检查 Edge，成功后按钮会显示绿色“浏览器正常”。
2. 在独立的“iTEST 账号”区域填写账号和密码，点击“验证登录”；通过后按钮变绿。
3. 在“答题模型”中选择 DeepSeek、OpenAI、GLM 或 Kimi，填写 API Key；需要时点击“验证模型”。更换密码、密钥或模型后，对应成功状态会清除。
4. 点击顶部“保存全部设置”，再前往“我的试卷”获取列表、选择试卷并开始填写。

默认仅填写供复核；开启“自动交卷”前请确认试卷。模型可能答错，调用模型服务可能产生费用。支持的题型、数据处理方式及构建信息见下文；仅在获得授权的场景使用。

模型设置只需选择服务商、填写 API Key，再点击顶部“保存全部设置”。模型名称和接口地址已预填，获取模型列表、修改接口及交卷等待收在“高级设置”中；验证模型为可选操作。切换服务商会保留各平台的密钥，旧配置保持可用。模型接口依据与历史调整见 [模型连接说明](MODEL_PRESETS.md)。

当前引擎支持标准单选、多选、下拉选择、文本填空与多行写作控件，可读取阅读材料及听力转写。口语、图片/视频、富文本和未识别控件会停止处理；综合真实试卷尚未全面验证，不能承诺覆盖全部考试。

首次驱动准备显示分阶段进度。若常规下载失败，会从同一微软官方地址重试，并校验版本后缓存。登录验证仅登录并读取试卷列表，不会开始考试；验证码可在测试浏览器中完成。默认窗口最大为 1120×820，并按屏幕工作区缩小。

## 本地数据与隐私

发布包中的账号、密码和密钥均为空，不包含开发者的配置、录音、试卷、截图或浏览器会话。
安装版将设置保存在 `%LOCALAPPDATA%\iTEST-Exam-Helper\config.yml`，缓存和日志位于同目录 `.exam_work`。
后台无法启动时，v1.2.1 会显示具体原因和系统编号，启动诊断位于 `.exam_work\startup.log`，只记录异常类型与编号，不记录账号、密码或密钥。可反馈该编号帮助排查；无需发送配置文件。
独立模型连接保存在同一数据目录的 `model_connections.yml`，保存的连接文件也含明文密钥。
设置以明文保存在当前 Windows 用户目录中，请勿分享该文件或整个数据目录。
卸载程序保留设置及缓存；如需清理，可在退出程序后自行删除上述数据目录。

## 原创图标与自动更新

v1.2.0 使用本项目原创“试卷与辅助星光”图标，替换原先的官方图标；安装程序、任务栏与官网使用同一图形。

程序启动后自动检查正式版本，常规自动检查间隔为 24 小时；已有待安装缓存时会重新确认版本。有新版时后台下载并校验 SHA-256。安装需要你确认，运行任务或浏览器尚未关闭时会阻止安装；确认后等待旧进程退出，再次校验文件并打开安装程序，原有配置保留。在“设置 → 应用与更新”可手动检查、取消下载或关闭自动检查与下载。

更新只访问本项目 GitHub 正式发布信息及附件，不发送 iTEST 账号、密码或 API Key。下载通过校验后才能打开安装程序；安装前再次校验文件，拒绝测试版、外部来源和不完整文件。

v1.1.0 及更早版本没有内置更新功能，需要先手动安装本次新版。更新偏好位于用户数据目录的 `update_settings.json`，安装包缓存位于 `.updates/`。

官网源码在 `website/`，通过 `.github/workflows/pages.yml` 发布到 GitHub Pages；页面不包含账号或密钥输入表单。

语音转写在本地完成；生成答案时会将题目、选项和转写文字发送给你配置的模型服务。
账号用于登录 iTEST；程序不会将账号密码发送给模型服务。

## 从源码运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item config.example.yml config.yml
.\.venv\Scripts\python.exe gui.py
```

运行前需要资源目录（不将大文件提交到 Git）：

- 将 [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip) 解压为 `model/`，确保存在 `model/am/final.mdl`。
- 从 [Gyan FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/) 获取 FFmpeg 7.1.1 essentials build，将 `ffmpeg.exe` 放入 `lib/`。许可证和源代码信息见 [第三方声明](THIRD_PARTY_NOTICES.md)。
- 不要复制个人 `config.yml`、`.exam_work`、`.driver-setup`、录音或浏览器缓存到公开仓库。

旧版命令行脚本保留在源码中，使用 `requirements.txt`；桌面安装版使用独立的新版引擎。

## 构建与检查

在 Windows x64 上使用 Python 3.13、锁定依赖及 Inno Setup 6.7.3：

```powershell
python -m unittest test_app_updates test_gui test_task_progress test_release test_exam_schema test_model_presets test_model_connections test_account_check test_browser_startup
New-Item -ItemType Directory -Force .release-tools
Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile .release-tools/MicrosoftEdgeWebview2Setup.exe
.\build_release.ps1 -ISCC 'C:\path\to\ISCC.exe'
```

构建产物位于 `release/`；`iTEST.spec` 只收集明确声明的资源。
`prepare_release.py` 是本地发布暂存工具，按白名单复制源文件，并对照本地配置检查敏感字段，不打印其内容。
GitHub Actions 支持手动构建，成功后生成可下载的安装包；推送 `v*` 标签时自动发布 Release。

安装包的离线检查覆盖界面、后台通信、依赖加载、语音模型及音频工具，未使用真实账号代替用户登录或提交试卷。
