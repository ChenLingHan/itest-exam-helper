# iTEST Exam Helper

Windows 桌面版 iTEST 英语考试辅助工具，基于 [YDHusky/itest](https://github.com/YDHusky/itest) 改进，采用 AGPL-3.0 许可证。非 iTEST 官方产品。

## 下载安装

在 [Releases](https://github.com/ChenLingHan/iTEST-exam-helper/releases/tag/v1.1.0-beta.3) 下载 `iTEST-Exam-Helper-1.1.0-beta.3-windows-x64-setup.exe`，双击安装，完成后从桌面或开始菜单打开 **iTEST**。

- 支持 Windows 10/11 64 位（x64），无需安装 Python 或手动安装依赖。
- 内置英语离线语音模型及 FFmpeg。
- 请安装 Microsoft Edge；缺少 WebView2 时，安装程序会提示安装 Microsoft 官方组件，需要联网。
- 首次获取试卷时，Selenium Manager 会联网下载与 Edge 匹配的驱动。
- 安装包未进行代码签名。发布页附 SHA256SUMS.txt，可用于核对下载文件。

## 首次使用

1. 打开“设置”，填写自己的 iTEST 账号、密码，搜索并选择服务商，填写 API Key，选择或输入模型 ID，然后保存连接和设置。
2. 点击获取试卷，在列表中选择目标试卷；需要考试码时填写考试码。
3. 默认只填写答案，完成后在 Edge 中检查；只有显式选择自动交卷并确认后才会提交。

项目目标是覆盖 iTEST 各类英语考试。当前测试版支持标准单选、多选、下拉选择、文本填空及多行写作控件，可读取阅读材料与听力转写，并在生成后逐题填写和核对。纯文字试卷无需语音转写。

本版通过合成页面及已有听力页面离线验证，尚未验证各类真实试卷的完整流程，不能承诺覆盖所有考试。口语录音、图片/视频题、富文本编辑器以及不认识的控件会停止处理；新页面结构需继续适配。默认不自动交卷。
模型生成的答案可能有误，应自行复核；使用模型服务可能产生费用。请仅在获得授权的场景使用。

模型设置采用连接管理方式：按官方服务、聚合平台和自定义分类搜索，提供 OpenRouter、硅基流动等聚合平台。同一服务商可保存多个独立命名的连接；每套连接保留自己的密钥、接口和模型。预设只填写起始值，地址和模型均可修改。旧配置自动迁入“原有模型配置”。

点击“获取模型列表”可查询平台的模型 ID，也可手动输入；平台列表不保证每个模型都支持文本对话和 JSON 输出。点击“测试连接”会发送一条简短 JSON 请求，可能消耗少量 Token。保存和切换不会自动调用模型。连接测试只验证当前接口与模型的兼容性，不代表答题准确率。参考来源及协议边界见 [模型连接说明](MODEL_PRESETS.md)。

## 本地数据与隐私

发布包中的账号、密码和密钥均为空，不包含开发者的配置、录音、试卷、截图或浏览器会话。
安装版将设置保存在 `%LOCALAPPDATA%\iTEST-Exam-Helper\config.yml`，缓存和日志位于同目录 `.exam_work`。
独立模型连接保存在同一数据目录的 `model_connections.yml`，保存的连接文件也含明文密钥。
设置以明文保存在当前 Windows 用户目录中，请勿分享该文件或整个数据目录。
卸载程序保留设置及缓存；如需清理，可在退出程序后自行删除上述数据目录。

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
python -m unittest test_gui test_task_progress test_release test_exam_schema test_model_presets test_model_connections
New-Item -ItemType Directory -Force .release-tools
Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile .release-tools/MicrosoftEdgeWebview2Setup.exe
.\build_release.ps1 -ISCC 'C:\path\to\ISCC.exe'
```

构建产物位于 `release/`；`iTEST.spec` 只收集明确声明的资源。
`prepare_release.py` 是本地发布暂存工具，按白名单复制源文件，并对照本地配置检查敏感字段，不打印其内容。
GitHub Actions 支持手动构建，成功后生成可下载的安装包；推送 `v*` 标签时自动发布 Release。

安装包的离线检查覆盖界面、后台通信、依赖加载、语音模型及音频工具，未使用真实账号代替用户登录或提交试卷。
