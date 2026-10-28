"""Official OpenAI-compatible endpoints, reviewed 2026-10-28. No credentials."""
from copy import deepcopy

PRESETS = [
    {'id': 'deepseek', 'label': 'DeepSeek', 'base_url': 'https://api.deepseek.com', 'model': 'deepseek-flash', 'hint': '填写 DeepSeek 开放平台的 API Key。', 'extra_body': {'thinking': {'type': 'disabled'}}},
    {'id': 'qwen-cn', 'label': '通义千问 · 北京', 'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'model': 'qwen-plus', 'hint': '使用阿里云百炼北京地域的 API Key。', 'extra_body': {'enable_thinking': False}},
    {'id': 'qwen-sg', 'label': '通义千问 · 新加坡', 'base_url': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'model': 'qwen-plus', 'hint': '使用阿里云百炼新加坡地域的 API Key。', 'extra_body': {'enable_thinking': False}},
    {'id': 'kimi', 'label': 'Kimi · 月之暗面', 'base_url': 'https://api.moonshot.cn/v1', 'model': 'kimi-k2.6', 'hint': '使用 Kimi 开放平台 API Key，不是 Kimi Code 订阅密钥。', 'extra_body': {'thinking': {'type': 'disabled'}}},
    {'id': 'zhipu', 'label': '智谱 GLM', 'base_url': 'https://open.bigmodel.cn/api/paas/v4', 'model': 'glm-5.2', 'hint': '使用智谱开放平台通用 API Key，不是 Coding Plan 专用密钥。', 'extra_body': {'thinking': {'type': 'disabled'}}},
    {'id': 'openai', 'label': 'OpenAI', 'base_url': 'https://api.openai.com/v1', 'model': 'gpt-4.1-mini', 'hint': '使用 OpenAI API Key；ChatGPT 订阅不包含 API 配额。'},
    {'id': 'gemini', 'label': 'Google Gemini', 'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai', 'model': 'gemini-3.8-flash', 'hint': '使用 Google AI Studio 的 Gemini API Key，需要能访问 Google 服务。'},
]

PRESETS += [
    {'id':'openrouter','label':'OpenRouter','base_url':'https://openrouter.ai/api/v1','model':'','hint':'填写 OpenRouter Key，然后获取模型列表或输入模型 ID。'},
    {'id':'siliconflow','label':'硅基流动','base_url':'https://api.siliconflow.cn/v1','model':'','hint':'填写硅基流动 Key，然后获取模型列表或输入模型 ID。'},
]
for _preset in PRESETS:
    _preset['category'] = 'aggregator' if _preset['id'] in ('openrouter','siliconflow') else 'official'
    _preset['aliases'] = {'qwen-cn':'阿里云 百炼 dashscope qwen tongyi','qwen-sg':'阿里云 百炼 新加坡 qwen',
        'zhipu':'智谱 glm bigmodel zhipu','kimi':'月之暗面 moonshot kimi','siliconflow':'硅基流动 siliconflow'} .get(_preset['id'],_preset['id'])
    _preset['protocol'] = 'OpenAI Chat Completions'


def get_presets():
    return deepcopy([p for p in PRESETS if p['id'] in ('deepseek','openai','zhipu','kimi')])


def infer_provider(ai):
    return next((p['id'] for p in PRESETS if p['base_url'].rstrip('/') == str(ai.get('base_url', '')).rstrip('/') and p['model'] == ai.get('model')), 'custom')


def normalize_ai(ai):
    result = deepcopy(ai)
    provider = result.get('provider', infer_provider(result))
    if provider != 'custom':
        preset = next((p for p in PRESETS if p['id'] == provider), None)
        if preset is None:
            raise ValueError('请选择有效的模型服务商，或选择自定义。')
        # A preset seeds a connection. User edits are retained when it is saved.
        result.setdefault('base_url',preset['base_url'])
        result.setdefault('model',preset['model'])
    result['provider'] = provider
    return result


def request_options(ai):
    # Apply provider-specific parameters only to that exact official preset.
    provider = infer_provider(ai)
    preset = next((p for p in PRESETS if p['id'] == provider), {})
    return {'extra_body': deepcopy(preset['extra_body'])} if preset.get('extra_body') else {}
