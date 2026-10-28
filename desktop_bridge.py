"""本地单窗口界面与 iTEST 后台的连接。界面不需要网络资源。"""
import copy
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import yaml
from task_progress import TaskProgress
from app_paths import DATA_ROOT, RESOURCE_ROOT, worker_command

ROOT = DATA_ROOT


def validate_config(config, need_ai=False):
    from urllib.parse import urlparse
    if not str(config.get('username','')).strip() or not config.get('password'):
        raise ValueError('请先在设置中填写 iTEST 账号和密码。')
    try: delay=float(config.get('sleep_time',10))
    except (ValueError,TypeError): raise ValueError('交卷等待时间需要是有效数字。') from None
    if not math.isfinite(delay) or delay<0: raise ValueError('交卷等待时间需要大于或等于 0。')
    config['sleep_time']=delay
    if need_ai:
        ai=config.get('ai',{})
        if not ai.get('apikey') or not str(ai.get('model','')).strip():
            raise ValueError('请先填写模型名称和 API Key。')
        url=urlparse(ai.get('base_url',''))
        if url.scheme not in ('http','https') or not url.hostname:
            raise ValueError('服务地址需要以 http:// 或 https:// 开头。')
    return config


class Bridge:
    def __init__(self,root=ROOT):
        self._root=Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock=threading.RLock()
        self._process=None
        self._window=None
        self._session=None
        self._pending=None
        self._notice_id=0
        self._allow_close=False
        self._close_after_stop=False
        self._task=None
        self._config={'username':'','password':'','sleep_time':10,'ai':{'base_url':'https://api.deepseek.com/v1','model':'deepseek-chat','apikey':''}}
        self._state={'version':0,'activity':'idle','busy':False,'stopping':False,'connected':False,'papers':[],
            'logs':[],'status':'准备就绪','notice':None,'progress':None,'task':None,'page':'papers','completed':False,'blocked_paper_ids':[]}
        try:
            file=self._root/'config.yml'
            if file.exists():
                value=yaml.safe_load(file.read_text(encoding='utf-8')) or {}
                if not isinstance(value,dict) or not isinstance(value.get('ai',{}),dict): raise ValueError()
                self._config.update({k:v for k,v in value.items() if k!='ai'})
                self._config['ai'].update(value.get('ai',{}))
        except Exception:
            self._state['page']='settings'
            self._notice('配置文件未能读取，请检查 config.yml 或重新填写设置。',True)

    def get_state(self):
        with self._lock: return copy.deepcopy(self._state)

    def get_config(self):
        with self._lock: return copy.deepcopy(self._config)

    def _redact(self,text):
        for config in (self._config,self._session or {}):
            for secret in (config.get('password'),config.get('ai',{}).get('apikey')):
                if secret: text=text.replace(str(secret),'***')
        return text

    def _touch(self): self._state['version']+=1

    def _notice(self,text,error=False,action=None,label='确认'):
        self._notice_id+=1
        self._pending=action
        self._state['notice']={'id':self._notice_id,'text':self._redact(text),'error':error,'confirm':action is not None,'label':label}
        self._touch()

    def _clear_notice(self):
        self._state['notice']=None; self._pending=None; self._touch()

    def dispatch(self,command):
        with self._lock:
            try:
                action=command.get('action')
                if action=='dismiss': self._clear_notice()
                elif action=='confirm':
                    notice=self._state['notice']
                    if notice and notice['id']==command.get('id') and self._pending:
                        pending=self._pending; self._clear_notice(); pending()
                elif action=='navigate':
                    page=command.get('page')
                    if page in ('papers','settings','logs'):
                        self._state['page']=page
                        if self._pending: self._clear_notice()
                elif action=='close': self._request_close()
                elif action=='stop':
                    if self._process and not self._state['stopping']:
                        self._notice('停止后将关闭本次浏览器。已填写或提交的内容不会撤销。',action=self._stop,label='停止任务')
                elif self._state['busy']:
                    return self.get_state()
                elif action=='save':
                    config=self._normalize(command.get('config',{}))
                    temp=self._root/'config.yml.tmp'
                    temp.write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False),encoding='utf-8')
                    temp.replace(self._root/'config.yml'); self._config=config
                    self._notice('设置已保存，重新获取试卷后生效。')
                elif action=='load':
                    # 未保存的表单配置也可用于本次登录。
                    config=self._normalize(command.get('config',self._config))
                    if self._process:
                        self._notice('重新获取会关闭当前浏览器，请先处理网页中尚未提交的答案。',action=lambda:self._load(config),label='重新获取')
                    else: self._load(config)
                elif action=='run': self._prepare_run(command)
                else: raise ValueError('不支持的操作。')
                self._touch()
            except Exception as error:
                self._notice(str(error) or type(error).__name__,True)
            return self.get_state()

    def _normalize(self,value):
        if not isinstance(value,dict) or not isinstance(value.get('ai',{}),dict): raise ValueError('设置格式错误。')
        config=copy.deepcopy(self._config)
        config.update({k:v for k,v in value.items() if k!='ai'})
        config['ai'].update(value.get('ai',{}))
        for key in ('username','password'):
            if not isinstance(config[key],str): raise ValueError('账号与密码格式错误。')
        for key in ('base_url','model','apikey'):
            if not isinstance(config['ai'].get(key),str): raise ValueError('模型配置格式错误。')
            config['ai'][key]=config['ai'][key].strip()
        config['username']=config['username'].strip()
        return validate_config(config)

    def _load(self,config):
        self._task=None
        self._state['task']=None
        self._config=config
        self._session=copy.deepcopy(config)
        self._state.update(papers=[],busy=True,activity='loading',completed=False,page='papers',status='正在登录并获取试卷…',progress=None)
        self._clear_notice()
        try: self._send({'action':'load','config':config})
        except Exception:
            self._state['busy']=False
            self._state['activity']='idle'
            raise

    def _prepare_run(self,command):
        if not self._process or not self._state['connected']: raise ValueError('请先获取试卷。')
        validate_config(self._session,True)
        # 表单修改后要求重新登录，以免实际使用旧的模型或账号。
        if self._normalize(command.get('config',self._config))!=self._session:
            raise ValueError('设置已修改，请重新获取试卷。')
        index=command.get('index')
        if not isinstance(index,int) or isinstance(index,bool) or not 0<=index<len(self._state['papers']):
            raise ValueError('请选择一张试卷。')
        paper=self._state['papers'][index]
        if str(paper.get('ksdId','')) in self._state['blocked_paper_ids']:
            raise ValueError('这张试卷本次已处理，请选择其他试卷。')
        code=str(command.get('exam_code','')).strip()
        if paper.get('examCodeFlag') and not code: raise ValueError('这张试卷需要考试码，请先填写。')
        submit=command.get('auto_submit') is True
        mode='完成后自动交卷' if submit else '仅填写答案，保留浏览器供检查'
        payload={'action':'run','index':index,'exam_code':code,'auto_submit':submit}
        self._notice(f'{paper.get("ksName","未命名")} · {paper.get("ksdId","")}\n{mode}。生成答案将使用模型 API 配额。',
            action=lambda:self._run(payload),label='确认开始')

    def _run(self,payload):
        self._task=TaskProgress(self._state['papers'][payload['index']],payload['auto_submit'])
        self._state['task']=self._task.snapshot()
        self._state.update(busy=True,activity='running',status='正在处理所选试卷…',progress=None,completed=False)
        try: self._send(payload)
        except Exception:
            self._state['busy']=False
            self._state['activity']='idle'
            self._task.fail('后台任务启动失败，请检查运行环境。')
            self._state['task']=self._task.snapshot()
            raise

    def _send(self,command):
        if self._process is None or self._process.poll() is not None:
            self._process=subprocess.Popen(worker_command(),cwd=RESOURCE_ROOT,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            threading.Thread(target=self._read,args=(self._process,),daemon=True).start()
        self._process.stdin.write(json.dumps(command,ensure_ascii=False)+'\n'); self._process.stdin.flush()
        self._state['connected']=True

    def _read(self,process):
        try:
            for line in process.stdout:
                try:
                    event=json.loads(line)
                    if isinstance(event,dict): self._event(process,event)
                except ValueError: pass
        finally:
            process.wait(); self._event(process,{'event':'exit'})

    def _event(self,process,event):
        with self._lock:
            if process is not self._process or self._state['stopping']: return
            kind=event.get('event')
            if kind=='log':
                message=self._redact(str(event['message']))
                self._state['logs']=(self._state['logs']+[message])[-600:]
                self._state['status']=message
                if self._task:
                    self._task.consume(message)
                    self._state['task']=self._task.snapshot()
                ratio=re.search(r'(\d+)/(\d+)',message)
                self._state['progress']=min(100,int(ratio[1])*100/int(ratio[2])) if ratio and int(ratio[2]) else None
            elif kind=='papers':
                self._state.update(papers=event['papers'],busy=False,activity='idle',status=f'已获取 {len(event["papers"])} 张试卷',completed=False)
            elif kind in ('done','error'):
                self._state.update(busy=False,activity='idle',completed=True,progress=None)
                if isinstance(event.get('papers'),list):
                    self._state['papers']=event['papers']
                    if kind=='done' and event.get('submitted') is True:
                        self._state['completed']=False
                text=('网站已确认提交成功。' if event.get('submitted') else '答案已填写，尚未交卷。请在浏览器中检查。') if kind=='done' else str(event['message'])
                self._state['status']='处理完成' if kind=='done' else '运行已停止'
                if self._task:
                    if kind=='done': self._task.finish(event.get('submitted') is True)
                    else: self._task.fail(self._redact(text))
                    self._state['task']=self._task.snapshot()
                    if kind=='done' or self._task.value['submitted']:
                        paper_id=self._task.value['paper_id']
                        if paper_id not in self._state['blocked_paper_ids']:
                            self._state['blocked_paper_ids'].append(paper_id)
                if event.get('refresh_error'):
                    text+=' 试卷列表更新失败，请稍后重新获取。'
                self._state['logs']=(self._state['logs']+[self._redact(text)])[-600:]
                self._notice(text,kind=='error')
            elif kind=='exit':
                if self._task and self._task.value['status']=='running':
                    self._task.fail('后台意外退出，请查看日志和网页。')
                    self._state['task']=self._task.snapshot()
                self._process=None; self._state.update(busy=False,activity='idle',connected=False,status='后台已退出，可重新获取试卷')
            self._touch()

    def _on_closing(self):
        with self._lock:
            if self._allow_close: return True
            if self._process:
                self._request_close(); return False
            return True

    def _request_close(self):
        if self._state['stopping']:
            self._close_after_stop=True
            return
        needs_confirmation=self._state['busy'] or (self._task and self._task.value['status'] in ('review','error') and not self._task.value['submitted'])
        if self._process and needs_confirmation:
            self._notice('退出将关闭本次浏览器，请先处理网页中的答案。',action=lambda:self._stop(close=True),label='退出程序')
        elif self._process:
            self._stop(close=True)
        else:
            threading.Thread(target=self._destroy_window,daemon=True).start()

    def _destroy_window(self):
        # destroy 会同步回调 _on_closing；必须在释放状态锁后调用。
        with self._lock:
            self._allow_close=True
            window=self._window
        if window: window.destroy()

    def _stop(self,close=False):
        self._close_after_stop=self._close_after_stop or close
        if self._state['stopping']: return
        self._state.update(stopping=True,busy=True,activity='stopping',status='正在关闭后台任务…')
        self._touch()
        threading.Thread(target=self._cleanup,args=(self._process,close),daemon=True).start()

    def _cleanup(self,process,close):
        try:
            if process and process.poll() is None:
                # 空闲后台能正常处理 close，并自行退出驱动；超时才结束本次进程树。
                try:
                    process.stdin.write(json.dumps({'action':'close'})+'\n')
                    process.stdin.flush()
                except (OSError,ValueError): pass
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    if os.name=='nt': subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=5)
                    else: process.terminate()
                    process.wait(timeout=3)
            if process: process.stdin.close()
            with self._lock:
                self._process=None
                if self._task and self._task.value['status']=='running':
                    self._task.fail('任务已由你停止，已填写或提交的答案不会撤销。',stopped=True)
                    self._state['task']=self._task.snapshot()
                self._state.update(stopping=False,busy=False,activity='idle',connected=False,papers=[],completed=False,status='已停止')
                self._touch()
                should_close=close or self._close_after_stop
            if should_close: self._destroy_window()
        except Exception:
            with self._lock:
                self._state.update(stopping=False,busy=False,activity='idle')
                self._close_after_stop=False
                self._notice('关闭后台任务失败，请重试。',True)
