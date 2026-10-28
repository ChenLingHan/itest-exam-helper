"""真实 WebView2 的离线交互检查，不访问网站或调用模型。"""
import base64
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import MagicMock
import webview
from desktop_bridge import Bridge
from task_progress import TaskProgress

ROOT=Path(__file__).resolve().parent
errors=[]


def check(window,bridge):
    try:
        window.events.loaded.wait(20)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelectorAll('.paper').length===2 && document.getElementById('username').value==='offline-test'"):
                break
            time.sleep(.2)
        else: raise AssertionError('界面或本地连接未就绪')
        assert window.evaluate_js("document.documentElement.scrollWidth<=innerWidth"), '小窗口出现横向溢出'
        assert window.evaluate_js("document.querySelector('#run').getBoundingClientRect().bottom<=innerHeight"), '操作按钮超出窗口'
        assert window.evaluate_js("document.querySelector('#cards img')===null && !window.injected"), '试卷名称被当作 HTML'
        window.evaluate_js("document.querySelector('.paper').click()")
        assert window.evaluate_js("!document.getElementById('run').disabled"), '选卷后不能开始'
        window.evaluate_js("document.getElementById('run').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and bridge.get_state()['notice'] is None: time.sleep(.1)
        notice=bridge.get_state()['notice']
        assert notice and notice['confirm'], '开始操作缺少窗口内确认'
        assert bridge._pending is not None
        bridge.dispatch({'action':'dismiss'})
        bridge._state['page']='settings'; bridge._touch()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#page-settings').classList.contains('active')"): break
            time.sleep(.2)
        assert window.evaluate_js("document.querySelector('#page-settings').classList.contains('active')"), '设置页未切换'
        assert window.evaluate_js("document.querySelector('#page-settings .content').scrollHeight>=document.querySelector('#page-settings .content').clientHeight"), '设置页滚动异常'
        assert window.evaluate_js("document.querySelectorAll('input[type=password]').length===2"), '密码与密钥未遮蔽'
        assert bridge._pending is None
        bridge._task=TaskProgress({'ksdId':'123','ksName':'离线进度检查'},True)
        bridge._task.consume('共 6 组、25 道题，需处理 33 份有效录音。')
        bridge._task.consume('正在转写录音 17/33...')
        bridge._state.update(page='papers',busy=True,task=bridge._task.snapshot())
        bridge._touch()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("!document.getElementById('taskProgress').hidden"): break
            time.sleep(.2)
        assert window.evaluate_js("document.getElementById('taskStage').textContent.includes('16/33')"), '转写计数把开始当成了完成'
        assert window.evaluate_js("document.getElementById('taskSteps').children.length===6"), '任务步骤未显示'
        assert window.evaluate_js("document.documentElement.scrollWidth<=innerWidth && document.querySelector('#run').getBoundingClientRect().bottom<=innerHeight"), '进度区导致小窗口操作区溢出'
        bridge._task.finish(False)
        bridge._state.update(busy=False,completed=True,task=bridge._task.snapshot())
        bridge._touch()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.getElementById('taskState').textContent.includes('未交卷')"): break
            time.sleep(.2)
        assert window.evaluate_js("document.getElementById('taskState').textContent.includes('未交卷')"), '待检查被误显示为已交卷'
        bridge._notice('答案已填写，尚未交卷，请在浏览器中检查。')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("!document.getElementById('notice').hidden"): break
            time.sleep(.2)
        assert window.evaluate_js("document.getElementById('notice').getBoundingClientRect().bottom<=innerHeight && document.querySelector('.dock').hidden"), '完成提示与任务进度挤压操作区'
        bridge._task.finish(True)
        bridge._state.update(completed=False,task=bridge._task.snapshot(),blocked_paper_ids=['123'])
        bridge._state['papers'][0]['canKaoshiJudgeBean']={'kaoshiBtnInfo':'已交卷'}
        bridge._touch()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('.paper .badge').textContent==='已交卷'"): break
            time.sleep(.2)
        assert window.evaluate_js("document.querySelector('.paper .badge').textContent==='已交卷' && document.querySelector('.paper').disabled"), '交卷状态未刷新或允许重复处理'
        window.evaluate_js("document.querySelectorAll('.paper')[1].click()")
        assert window.evaluate_js("!document.getElementById('run').disabled && !document.querySelector('.dock').hidden && document.getElementById('taskProgress').classList.contains('compact')"), '完成后不能选择下一张试卷'
        bridge._state.update(activity='loading',busy=True,task=None)
        bridge._touch()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#refresh svg').classList.contains('spinner')"): break
            time.sleep(.2)
        assert window.evaluate_js("document.querySelector('#refresh svg').classList.contains('spinner')"), '获取试卷时未显示加载状态'
        bridge._state.update(activity='stopping',stopping=True,busy=True,status='正在关闭后台任务…')
        bridge._touch()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.getElementById('statusText').textContent.includes('正在关闭')"): break
            time.sleep(.2)
        assert window.evaluate_js("!document.querySelector('#refresh svg').classList.contains('spinner') && document.querySelector('#refresh span').textContent==='获取试卷' && document.getElementById('progress').hidden && document.getElementById('skeleton').hidden"), '关闭时仍显示获取试卷的加载动画'
        print('WebView2: bridge, cards, selection, inline confirmation, safe text, settings, and minimum layout OK',flush=True)
    except Exception as error:
        errors.append(str(error)); print('UI CHECK FAILED:',error,flush=True)
    finally:
        window.destroy()


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder:
        bridge=Bridge(folder)
        bridge._config={'username':'offline-test','password':'test-password','sleep_time':1,'ai':{'model':'test-model','apikey':'test-key','base_url':'https://example.com/v1'}}
        bridge._session=bridge._config.copy()
        bridge._process=MagicMock()
        bridge._state.update(connected=True,papers=[{'ksdId':'123','ksName':'示例英语听力'}, {'ksdId':'456','ksName':'<img src=x onerror=window.injected=1>'}])
        html=(ROOT/'ui/index.html').read_text(encoding='utf-8').replace('__ITEST_ICON__','data:image/png;base64,'+base64.b64encode((ROOT/'assets/itest-icon-32.png').read_bytes()).decode())
        window=webview.create_window('iTEST offline UI check',html=html,js_api=bridge,width=680,height=480,hidden=True)
        webview.start(check,(window,bridge),gui='edgechromium',private_mode=True)
    raise SystemExit(bool(errors))
