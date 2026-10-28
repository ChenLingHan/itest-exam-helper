# 模型服务预设

核对日期：2026-10-28。选择服务商即可自动填写接口地址和模型；只需填写该平台的 API Key。已有配置保持原值，不自动迁移到新模型。新服务商初始 Key 为空；来回切换会恢复各自的草稿，不会跨平台沿用同一个 Key。

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


## v1.1.0-beta.3 连接管理

交互参考 [CC Switch 添加配置](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/2-providers/2.1-add.md) 与 [编辑配置](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/2-providers/2.3-edit.md)。借鉴分类搜索、独立连接及编辑模型的方式，代码独立实现，没有复制其预设代码。

- 新增 [OpenRouter](https://openrouter.ai/docs/quickstart) 和 [硅基流动](https://docs.siliconflow.cn/docs/userguide/quickstart)。这类平台不指定固定模型，填 Key 后获取模型列表或手动输入。
- 官方服务的预设模型可修改；模型列表来自所填写平台的 `/models` 接口，部分平台可能不提供，届时可手动输入。
- 模型与 JSON 连接测试是显式操作，会产生一次小请求；保存、切换和启动软件不自动调用 API。
- 独立配置保存到 `model_connections.yml`，列表状态不包含密钥，未保存的连接草稿仅留在当前窗口内存。退出前需保存。
- 顶部“保存设置”也会保存已填写 Key 的模型连接；切换后重新获取试卷才会更新正在使用的后台配置。
- 当前支持 OpenAI Chat Completions 兼容协议。CC Switch 中的 OAuth 登录、Coding Plan 特定协议及原生 Anthropic/Responses 路由没有照搬为可用功能。

以上是交互和接口格式验证，未以真实密钥对所有平台进行计费调用。
