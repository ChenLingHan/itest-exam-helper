# 桌面界面

本地 HTML/CSS/JavaScript，由 pywebview 调用系统 WebView2 渲染；不加载远程脚本、字体或样式。原 Python 答题引擎通过独立后台进程运行。

设计参考：
- [CC Switch 官方项目](https://github.com/farion1231/cc-switch)
- [官方界面截图](https://github.com/farion1231/cc-switch/blob/main/assets/release-notes/v4.0.0/main-zh.png)
- [官方样式与设计变量](https://github.com/farion1231/cc-switch/blob/main/src/index.css)

本界面的 CSS、SVG 图标及业务交互独立编写，沿用项目的 iTEST 官方标志。侧栏、试卷卡片、设置、日志和确认区域都在同一窗口内。试卷名称和日志始终以纯文本显示；密码、密钥不写入界面状态或日志。表单中的配置只在当前窗口内存中使用，保存时写入现有 config.yml。

运行检查：`python -m unittest test_gui -v`；Windows 真实界面离线检查：`python test_desktop_ui.py`。
