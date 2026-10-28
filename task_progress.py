"""按真实工作阶段汇总进度；流程百分比不代表耗时百分比。"""
import copy
import re
import time

STAGES=(('enter','进入试卷','次'),('download','下载录音','份'),('transcribe','转写录音','份'),
        ('generate','生成答案','组'),('fill','填写核对','题'),('submit','交卷确认','次'))


class TaskProgress:
    def __init__(self,paper,auto_submit,clock=time.time):
        self.clock=clock
        self.value={'paper_id':str(paper.get('ksdId','')),'paper_name':paper.get('ksName','未命名试卷'),
            'auto_submit':auto_submit,'status':'running','stage':'enter','started_at':clock(),
            'finished_at':None,'detail':'正在进入所选试卷','submitted':False,'submit_at':None,
            'stages':[{'key':key,'title':title,'unit':unit,'state':'pending','done':0,'total':1 if key in ('enter','submit') else None,'active':None} for key,title,unit in STAGES]}
        self._stage('enter')
        if not auto_submit: self._get('submit')['state']='manual'

    def _get(self,key): return next(stage for stage in self.value['stages'] if stage['key']==key)

    def _stage(self,key):
        if self.value['status']!='running': return
        for stage in self.value['stages']:
            if stage['key']==key:
                if stage['state']!='complete': stage['state']='running'
                break
            if stage['state']!='manual':
                stage['state']='complete'
                if stage['total'] is not None: stage['done']=stage['total']
        self.value['stage']=key

    def _count(self,key,done,total,complete=False):
        self._stage(key)
        stage=self._get(key)
        stage.update(done=max(0,min(done,total)),total=total)
        if complete and done>=total: stage['state']='complete'

    def consume(self,message):
        if self.value['status']!='running': return
        match=re.search(r'共\s*(\d+)\s*组、\s*(\d+)\s*道题，需处理\s*(\d+)\s*份',message)
        if match:
            groups,questions,audio=map(int,match.groups())
            for key,total in (('download',audio),('transcribe',audio),('generate',groups),('fill',questions)):
                self._get(key)['total']=total
            self._stage('download' if audio else 'generate'); self.value['detail']='开始下载对应听力录音' if audio else '纯文字试卷，无需录音，正在准备答案'
        elif '题目页面已就绪' in message:
            stage=self._get('enter'); stage.update(done=1,state='complete')
            self.value['detail']='试卷已就绪，正在读取题目'
        elif (match:=re.search(r'录音下载\s*(\d+)/(\d+)',message)):
            done,total=map(int,match.groups()); self._count('download',done,total,True)
            self.value['detail']=f'已下载 {done}/{total} 份录音'
        elif (match:=re.search(r'正在转写录音\s*(\d+)/(\d+)',message)):
            active,total=map(int,match.groups())
            # “正在转写第 N 份”只证明前 N-1 份完成。
            stage=self._get('transcribe'); done=max(stage['done'],active-1)
            self._count('transcribe',done,total)
            stage['active']=active; self.value['detail']=f'正在处理第 {active} 份录音，已完成 {done}/{total} 份'
        elif (match:=re.search(r'录音转写完成\s*(\d+)/(\d+)',message)):
            done,total=map(int,match.groups()); self._count('transcribe',done,total,True)
            self._get('transcribe')['active']=None
            self.value['detail']=f'已转写 {done}/{total} 份录音'
        elif '正在生成答案' in message:
            self._stage('generate'); self.value['detail']='题目材料已就绪，正在等待模型返回答案'
        elif (match:=re.search(r'答案生成\s*(\d+)/(\d+)',message)):
            done,total=map(int,match.groups()); self._count('generate',done,total,True)
            self.value['detail']=f'已生成并校验 {done}/{total} 组答案'
        elif (match:=re.search(r'答案已填入\s*(\d+)/(\d+)',message)):
            done,total=map(int,match.groups()); self._count('fill',done,total)
            self.value['detail']=f'已填写 {done}/{total} 题'+('，正在核对选项' if done==total else '')
        elif (match:=re.search(r'已核对\s*(\d+)\s*道题全部(?:选中|填写)',message)):
            total=int(match[1]); self._count('fill',total,total,True)
            self.value['detail']=f'{total} 道题已全部填写并通过核对'
        elif (match:=re.search(r'答案核对完成，\s*([\d.]+)\s*秒后交卷',message)):
            self._stage('submit'); self.value['submit_at']=self.clock()+float(match[1])
            self.value['detail']='答案已核对，等待设置的交卷时间'
        elif '已确认交卷，正在等待网站结果' in message:
            self._stage('submit'); self.value['submit_at']=None
            self.value['detail']='已点击交卷，正在等待网站确认'
        elif '网站已确认提交成功' in message:
            self._stage('submit'); self.value['submitted']=True
            self.value['detail']='网站已接收答案，正在核对试卷列表状态'

    def finish(self,submitted):
        self.value.update(submitted=submitted,status='submitted' if submitted else 'review',finished_at=self.clock(),submit_at=None)
        for stage in self.value['stages']:
            if stage['key']=='submit' and not submitted:
                stage['state']='manual'
            else:
                stage['state']='complete'
                if stage['total'] is not None: stage['done']=stage['total']
        self.value['detail']='网站已确认提交成功' if submitted else '答案已全部填写并核对，尚未交卷，请在浏览器中检查'

    def fail(self,message,stopped=False):
        self.value.update(status='stopped' if stopped else 'error',finished_at=self.clock(),submit_at=None,detail=message)
        current=self._get(self.value['stage'])
        if current['state']!='complete': current['state']='stopped' if stopped else 'error'

    def snapshot(self):
        value=copy.deepcopy(self.value)
        steps=[stage for stage in value['stages'] if stage['state']!='manual']
        completed=sum(stage['state']=='complete' for stage in steps)
        fraction=0
        active=self._get(value['stage'])
        if active['state']!='complete' and active['total']:
            fraction=min(.95,active['done']/active['total'])
        value.update(completed_steps=completed,total_steps=len(steps),percent=min(99,int((completed+fraction)/len(steps)*100)))
        if value['status'] in ('submitted','review'): value['percent']=100
        return value
