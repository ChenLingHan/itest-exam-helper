"""Named local connections and explicit model discovery/JSON compatibility checks."""
from copy import deepcopy
import json
from pathlib import Path
import uuid
from urllib.parse import urlparse
import yaml
from model_presets import normalize_ai, request_options


def checked_ai(value, need_model=True):
    if not isinstance(value,dict):
        raise ValueError('模型配置格式错误。')
    ai=normalize_ai(value)
    for key in ('base_url','model','apikey'):
        if not isinstance(ai.get(key),str):
            raise ValueError('模型配置格式错误。')
        ai[key]=ai[key].strip()
    url=urlparse(ai['base_url'])
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('请填写有效的 API 基础地址，不要填写 /chat/completions 或附带账号参数。')
    if url.path.rstrip('/').endswith(('/chat/completions','/models')):
        raise ValueError('请填写 API 基础地址，不要附加 /chat/completions 或 /models。')
    if not ai['apikey']:
        raise ValueError('请先填写这套连接的 API Key。')
    if need_model and not ai['model']:
        raise ValueError('请选择或输入模型 ID。')
    return ai


class Connections:
    def __init__(self,root,legacy):
        self.path=Path(root)/'model_connections.yml'
        self.data={'version':1,'active_id':None,'connections':[]}
        if self.path.exists():
            data=yaml.safe_load(self.path.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or not isinstance(data.get('connections'),list):
                raise ValueError('模型连接文件格式错误，请检查 model_connections.yml。')
            rows=data['connections']
            if any(not isinstance(r,dict) or not isinstance(r.get('id'),str) or not isinstance(r.get('name'),str) or not isinstance(r.get('ai'),dict) for r in rows):
                raise ValueError('模型连接文件格式错误。')
            if len({r['id'] for r in rows}) != len(rows):
                raise ValueError('模型连接编号重复。')
            self.data=data
        elif legacy.get('apikey'):
            self.data['connections']=[{'id':'migrated','name':'原有模型配置','ai':deepcopy(legacy)}]
            self.data['active_id']='migrated'
            self._write(self.data)

    def _write(self,data):
        temp=self.path.with_suffix('.yml.tmp')
        temp.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
        temp.replace(self.path)
        self.data=data

    def summary(self):
        return {'active_id':self.data.get('active_id'),'connections':[
            {'id':r['id'],'name':r['name'],'provider':r['ai'].get('provider','custom'),
             'model':r['ai'].get('model',''),'has_key':bool(r['ai'].get('apikey'))} for r in self.data['connections']]}

    def get(self,key):
        row=next((r for r in self.data['connections'] if r['id']==key),None)
        if row is None:
            raise ValueError('找不到该模型连接。')
        return deepcopy(row)

    def save(self,key,name,ai):
        if not isinstance(name,str) or not name.strip() or len(name.strip())>80:
            raise ValueError('请填写连接名称（最多 80 字）。')
        ai=checked_ai(ai)
        data=deepcopy(self.data)
        if key is not None:
            self.get(key)
        key=key or uuid.uuid4().hex
        row={'id':key,'name':name.strip(),'ai':ai}
        data['connections']=[r for r in data['connections'] if r['id']!=key]+[row]
        data['active_id']=key
        self._write(data)
        return deepcopy(row)

    def activate(self,key):
        row=self.get(key)
        data=deepcopy(self.data);data['active_id']=key;self._write(data)
        return row

    def secrets(self):
        return [r['ai'].get('apikey') for r in self.data['connections']]


def model_tool(ai,kind):
    """Called only by explicit user actions. No automatic probes on save/switch."""
    from openai import OpenAI
    ai=checked_ai(ai,need_model=kind=='test')
    client=OpenAI(api_key=ai['apikey'],base_url=ai['base_url'],timeout=25,max_retries=0)
    try:
        if kind=='models':
            page=client.models.list()
            models=sorted({m.id for m in page.data if isinstance(m.id,str) and 0<len(m.id)<=256})[:5000]
            return {'ok':True,'models':models,'message':f'已获取 {len(models)} 个模型；请选择支持文本对话和 JSON 输出的模型。'}
        if kind!='test':
            raise ValueError('不支持的模型检查操作。')
        response=client.chat.completions.create(model=ai['model'],messages=[
            {'role':'system','content':'Return only a JSON object: {"ok":true}.'},
            {'role':'user','content':'Check JSON output.'}],response_format={'type':'json_object'},max_tokens=128,**request_options(ai))
        choice=response.choices[0]
        if choice.finish_reason!='stop' or json.loads(choice.message.content or '{}').get('ok') is not True:
            return {'ok':False,'message':'接口已返回，但 JSON 输出检查未通过。请换用支持 JSON 输出的文本模型。'}
        return {'ok':True,'message':'连接与 JSON 输出检查通过。该检查仅验证接口兼容性，不代表答题准确率。'}
    finally:
        client.close()


def tool_error(error):
    # Never return SDK exception strings: upstream responses may echo credentials.
    status=getattr(error,'status_code',None)
    if status in (401,403): return '鉴权失败：请检查 API Key、所属地域及模型权限。'
    if status==404: return '接口或模型不存在；若平台不提供模型列表，请手动填写模型 ID。'
    if status==429: return '请求受限或配额不足，请查看平台余额及限流设置。'
    return '请求未完成：请检查网络、接口地址及模型是否支持当前操作。'
