"""iTEST 现代单窗口入口：系统 WebView2 + 本地界面。"""
import base64
import os
import sys
import json
import time
from pathlib import Path
from desktop_bridge import Bridge, validate_config
from app_paths import RESOURCE_ROOT

ROOT=RESOURCE_ROOT


def initial_window_size(work_width=1440,work_height=900):
    # Logical pixels; leave room for the taskbar, title bar, and window borders.
    available_width=max(320,int(work_width)-40)
    available_height=max(320,int(work_height)-60)
    width=min(1120,available_width)
    height=min(820,available_height)
    return width,height,(min(680,width),min(480,height))


def screen_work_area():
    if os.name=='nt':
        try:
            import ctypes
            from ctypes import wintypes
            rect=wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48,0,ctypes.byref(rect),0):
                try: scale=ctypes.windll.user32.GetDpiForSystem()/96
                except Exception: scale=1
                return (rect.right-rect.left)/scale,(rect.bottom-rect.top)/scale
        except Exception: pass
    return 1440,900


def main():
    import webview
    smoke='--smoke-test' in sys.argv
    if os.name=='nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('iTEST.ListeningAssistant')
        ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
        mutex_name='Local\\iTEST.ModernDesktop.Smoke' if smoke else 'Local\\iTEST.ModernDesktop'
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,mutex_name)
        if ctypes.windll.kernel32.GetLastError()==183: return
    api=Bridge()
    html=(ROOT/'ui'/'index.html').read_text(encoding='utf-8')
    logo=base64.b64encode((ROOT/'assets'/'itest-icon-32.png').read_bytes()).decode()
    html=html.replace('__APP_STYLES__',(ROOT/'ui/app.css').read_text(encoding='utf-8'))
    html=html.replace('__NOTIFICATIONS_SCRIPT__',(ROOT/'ui/notifications.js').read_text(encoding='utf-8'))
    html=html.replace('__MODEL_SETTINGS_SCRIPT__',(ROOT/'ui'/'model-settings.js').read_text(encoding='utf-8'))
    html=html.replace('__ITEST_ICON__','data:image/png;base64,'+logo)
    width,height,minimum=initial_window_size(*screen_work_area())
    window=webview.create_window('iTEST',html=html,js_api=api,width=width,height=height,min_size=minimum,hidden=smoke,
        background_color='#ffffff',text_select=True,confirm_close=False)
    api._window=window
    window.events.closing+=api._on_closing
    def check():
        report={'ok':False}
        try:
            if not window.events.loaded.wait(30): raise RuntimeError('WebView2 load timeout')
            if not window.evaluate_js("document.getElementById('username')!==null && document.getElementById('run')!==null"):
                raise RuntimeError('UI controls missing')
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if window.evaluate_js("document.querySelectorAll('.provider-card').length===5 && document.getElementById('statusText').textContent!=='正在连接本地服务…' && getComputedStyle(document.getElementById('browserSection')).backgroundColor==='rgb(255, 255, 255)'"):
                    break
                time.sleep(.1)
            else: raise RuntimeError('New settings layout did not finish loading')
            api._send({'action':'close'})
            process=api._process
            if process and process.wait(timeout=20)!=0: raise RuntimeError('Worker failed')
            report={'ok':True,'webview2':True,'worker_pipe':True,'blank_config':not api._config['username']}
        except Exception as error:
            report={'ok':False,'error':str(error)}
        finally:
            Path(sys.argv[sys.argv.index('--smoke-test')+1]).write_text(json.dumps(report),encoding='utf-8')
            api._allow_close=True
            window.destroy()
    webview.start(check if smoke else None,gui='edgechromium',private_mode=True,icon=str(ROOT/'assets'/'itest.ico'))


if __name__=='__main__':
    os.chdir(ROOT)
    main()
