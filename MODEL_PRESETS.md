# 模型服务预设

核对日期：2026-10-28。选择服务商即可自动填写接口地址和模型；只需填写该平台的 API Key。已有配置保持原值，不自动迁移到新模型。更换服务商会清空界面中的 Key，避免跨平台发送。

| 预设 | 默认模型 | 官方依据 |
| --- | --- | --- |
| DeepSeek | deepseek-flash | [快速开始](https://api-docs.deepseek.com/)、[JSON 输出](https://api-docs.deepseek.com/guides/json_mode/) |
| 通义千问（北京/新加坡） | qwen-plus | [OpenAI 兼容接口](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[思考参数与模型](https://help.aliyun.com/zh/model-studio/deep-thinking) |
| Kimi | kimi-k2.6 | [快速开始](https://platform.kimi.com/docs/get-api-key)、[K2.6](https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart) |
| 智谱 GLM | glm-5.2 | [OpenAI 兼容接口](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction) |
| OpenAI | gpt-4.1-mini | [模型说明](https://developers.openai.com/api/docs/models/gpt-4.1-mini) |
| Google Gemini | gemini-3.8-flash | [OpenAI 兼容接口](https://ai.google.dev/gemini-api/docs/openai/) |

默认优先采用可关闭思考、适合结构化输出的配置；不代表各平台最新或最强模型。百炼预设使用官方仍支持的公共域名，不需要额外填写业务空间 ID；Key 必须与北京/新加坡地域匹配。Google 等服务还需要可达的网络及可用地域。订阅产品（例如 ChatGPT、Kimi Code、GLM Coding Plan）不等同于这里使用的通用 API Key。

预设包含官方接口参数及离线请求构造检查，未使用真实密钥对所有平台进行计费调用。模型可用性、账号权限、余额和网络由各服务商决定。如需其他模型或中转服务，选择“自定义”并填写接口地址及模型名称。
