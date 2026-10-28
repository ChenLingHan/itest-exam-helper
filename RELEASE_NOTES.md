# v1.1.0-beta.2

- 修复获取试卷时 No module named selenium.webdriver.edge.options：补齐 Selenium 的动态模块和 Selenium Manager。
- 打包自检增加 EdgeOptions、驱动类、Manager 文件检查，并实际启动无账号空白 Edge 页面，避免仅导入主模块的检查漏报。
- 模型设置新增 DeepSeek、通义千问（北京/新加坡）、Kimi、智谱 GLM、OpenAI、Gemini 预设；选择服务商后填写 API Key 即可。
- 保留自定义兼容接口和旧配置。切换服务商清空密钥，避免把同一密钥发给其他服务商。
- 预设按官方文档核对并覆盖请求构造测试，未使用真实密钥进行各平台计费调用；地域、模型权限及网络仍需用户账号支持。

保持测试版状态，题型覆盖限制见 README。可直接覆盖安装，设置保存在用户目录。
