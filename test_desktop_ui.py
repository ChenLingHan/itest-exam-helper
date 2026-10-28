"""真实 WebView2 的离线交互检查，不访问网站或调用模型。"""
import base64
import os
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import MagicMock, patch
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
        assert window.evaluate_js("document.querySelector('#paperGuide .current').dataset.step==='2'"), 'Next step must point to paper selection'
        window.evaluate_js("document.querySelector('.paper').click()")
        assert window.evaluate_js("document.querySelector('#paperGuide .current').dataset.step==='3'"), 'Next step must point to starting'
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
        assert window.evaluate_js("document.querySelectorAll('.provider-card').length===5 && document.querySelector('#provider').value==='custom'"), '预设目录或旧配置识别错误'
        window.evaluate_js("document.querySelector('#apikey').value='private-test-key'; [...document.querySelectorAll('.provider-card')].find(b=>b.textContent.includes('DeepSeek')).click()")
        assert window.evaluate_js("document.querySelector('#apikey').value==='' && document.querySelector('#model').value==='deepseek-flash' && !document.querySelector('#model').readOnly"), '新平台携带了旧 Key 或模型被锁死'
        window.evaluate_js("document.querySelector('#model').value='my-deepseek-model';document.querySelector('#apikey').value='deepseek-private-test';[...document.querySelectorAll('.provider-card')].find(b=>b.textContent.includes('自定义')).click()")
        assert window.evaluate_js("document.querySelector('#apikey').value==='private-test-key' && document.querySelector('#advanced').open"), '旧平台的未保存草稿丢失'
        window.evaluate_js("[...document.querySelectorAll('.provider-card')].find(b=>b.textContent.includes('DeepSeek')).click()")
        assert window.evaluate_js("document.querySelector('#apikey').value==='deepseek-private-test' && document.querySelector('#model').value==='my-deepseek-model'"), '来回切换未保留独立模型与密钥'
        window.evaluate_js("document.querySelector('#saveConnection').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and not bridge.get_connections()['connections']: time.sleep(.05)
        assert len(bridge.get_connections()['connections'])==1, '连接未持久化'
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#connectionResult').textContent.includes('已保存')"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelectorAll('.connection-card').length===1"), '已保存连接未显示'
        window.evaluate_js("document.querySelector('#newConnection').click()")
        assert window.evaluate_js("document.querySelector('#apikey').value===''")
        window.evaluate_js("document.querySelector('.connection-card').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#apikey').value==='deepseek-private-test'"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelector('#model').value==='my-deepseek-model' && document.querySelector('#apikey').value==='deepseek-private-test'"), '连接切换未恢复模型与 Key'
        window.evaluate_js("document.querySelector('#model').value='deepseek-flash';document.querySelector('#model').dispatchEvent(new Event('input'));document.querySelector('#toggleModels').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelectorAll('.model-option').length===2"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelectorAll('.model-option').length===2 && !document.querySelector('#modelPicker').hidden && document.querySelector('#model').getAttribute('list')===null"), '获取两个模型后仍被当前输入值过滤'
        window.evaluate_js("[...document.querySelectorAll('.model-option')].find(b=>b.textContent==='deepseek-v4-pro').click()")
        assert window.evaluate_js("document.querySelector('#model').value==='deepseek-v4-pro' && document.querySelector('#modelPicker').hidden"), '不能选择另一个模型'
        bridge._touch();time.sleep(.5)
        assert window.evaluate_js("document.querySelector('#modelPicker').hidden"), '旧请求结果重复打开列表'
        window.evaluate_js("document.querySelector('#toggleModels').click();document.querySelector('#modelSearch').value='flash';document.querySelector('#modelSearch').dispatchEvent(new Event('input'))")
        assert window.evaluate_js("document.querySelectorAll('.model-option').length===1 && document.querySelector('.model-option').textContent==='deepseek-flash'"), '独立模型搜索失败'
        window.evaluate_js("document.querySelector('#base_url').value='https://different.example/v1';document.querySelector('#base_url').dispatchEvent(new Event('input'))")
        assert window.evaluate_js("document.querySelectorAll('.model-option').length===0 && document.querySelector('#modelPicker').hidden"), '修改接口后沿用了旧模型列表'
        assert 'deepseek-private-test' not in json.dumps(bridge.get_state()), '状态中泄露 Key'
        window.evaluate_js("document.querySelector('#testAccount').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#accountTestResult').textContent.includes('登录测试通过')"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelector('#accountTestResult').textContent.includes('登录测试通过')"), 'iTEST 登录测试结果未显示'
        assert len(bridge.get_state()['papers'])==2, '登录测试改动了已有试卷列表'
        window.evaluate_js("document.querySelector('#testBrowser').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#browserTestResult').textContent.includes('Edge 启动检查通过')"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelector('#browserTestResult').textContent.includes('Edge 启动检查通过')"), '独立浏览器检查结果未显示'
        assert window.evaluate_js("document.querySelector('#browserSection #testBrowser')!==null && document.querySelector('#accountSection #testBrowser')===null"), '浏览器检查仍位于账号区'
        assert window.evaluate_js("document.querySelector('#testBrowser').classList.contains('is-success') && document.querySelector('#testAccount').classList.contains('is-success')"), '检查通过后按钮没有分别变绿'
        assert window.evaluate_js("document.querySelector('#browserReady').classList.contains('passed') && document.querySelector('#accountReady').classList.contains('passed')"), '检查摘要状态未更新'
        if window.evaluate_js('innerWidth')>950:
            assert window.evaluate_js("Math.abs(document.querySelector('#username').getBoundingClientRect().top-document.querySelector('#testAccount').getBoundingClientRect().top)<2"), '账号密码与验证按钮没有同排'
        window.evaluate_js("document.querySelector('#password').value='changed-password';document.querySelector('#password').dispatchEvent(new Event('input'))")
        assert window.evaluate_js("!document.querySelector('#testAccount').classList.contains('is-success') && document.querySelector('#testBrowser').classList.contains('is-success')"), '修改密码后错误沿用绿色登录状态'
        window.evaluate_js("document.querySelector('#testModel').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#testModel').classList.contains('is-success')"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelector('#testModel').classList.contains('is-success')"), '模型验证成功后没有绿色反馈'
        window.evaluate_js("document.querySelector('#saveConnection').click()")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if window.evaluate_js("document.querySelector('#connectionResult').textContent.includes('已保存')"): break
            time.sleep(.05)
        assert window.evaluate_js("document.querySelector('#testModel').classList.contains('is-success')"), '保存相同配置后丢失成功状态'
        window.evaluate_js("document.querySelector('#model').value='changed-model';document.querySelector('#model').dispatchEvent(new Event('input'))")
        assert window.evaluate_js("!document.querySelector('#testModel').classList.contains('is-success')"), '更换模型后沿用旧验证结果'
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
        bridge._state.update(page='papers',connected=True,papers=[{'ksdId':'123','ksName':'示例英语听力'}, {'ksdId':'456','ksName':'<img src=x onerror=window.injected=1>'}])
        html=(ROOT/'ui/index.html').read_text(encoding='utf-8').replace('__APP_STYLES__',(ROOT/'ui/app.css').read_text(encoding='utf-8')).replace('__MODEL_SETTINGS_SCRIPT__',(ROOT/'ui/model-settings.js').read_text(encoding='utf-8')).replace('__ITEST_ICON__','data:image/png;base64,'+base64.b64encode((ROOT/'assets/itest-icon-32.png').read_bytes()).decode())
        test_width,test_height=map(int,os.environ.get('ITEST_UI_TEST_SIZE','680x480').split('x'))
        window=webview.create_window('iTEST offline UI check',html=html,js_api=bridge,width=test_width,height=test_height,hidden=True)
        with patch('desktop_bridge.model_tool',side_effect=lambda value,kind:{'ok':True,'models':['deepseek-flash','deepseek-v4-pro'],'message':'已获取 2 个模型'} if kind=='models' else {'ok':True,'message':'模型连接验证通过'}), patch.object(bridge,'_send',side_effect=lambda command: bridge._event(bridge._process,{'event':'account-test','request_id':command['request_id'],'ok':True,'message':'Edge 启动检查通过' if command['action']=='check_browser' else '登录测试通过，可读取试卷列表。'}) if command['action'] in ('check_login','check_browser') else None):
            webview.start(check,(window,bridge),gui='edgechromium',private_mode=True)
    raise SystemExit(bool(errors))
