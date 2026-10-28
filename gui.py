"""iTEST 现代单窗口入口：系统 WebView2 + 本地界面。"""
import base64
import os
import sys
import json
from pathlib import Path
from desktop_bridge import Bridge, validate_config
from app_paths import RESOURCE_ROOT

ROOT=RESOURCE_ROOT


def main():
    import webview
    if os.name=='nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('iTEST.ListeningAssistant')
        ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Local\\iTEST.ModernDesktop')
        if ctypes.windll.kernel32.GetLastError()==183: return
    api=Bridge()
    smoke='--smoke-test' in sys.argv
    html=(ROOT/'ui'/'index.html').read_text(encoding='utf-8')
    logo=base64.b64encode((ROOT/'assets'/'itest-icon-32.png').read_bytes()).decode()
    html=html.replace('__MODEL_SETTINGS_SCRIPT__',(ROOT/'ui'/'model-settings.js').read_text(encoding='utf-8'))
    html=html.replace('__ITEST_ICON__','data:image/png;base64,'+logo)
    window=webview.create_window('iTEST',html=html,js_api=api,width=860,height=600,min_size=(680,480),hidden=smoke,
        background_color='#ffffff',text_select=True,confirm_close=False)
    api._window=window
    window.events.closing+=api._on_closing
    def check():
        report={'ok':False}
        try:
            if not window.events.loaded.wait(30): raise RuntimeError('WebView2 load timeout')
            if not window.evaluate_js("document.getElementById('username')!==null && document.getElementById('run')!==null"):
                raise RuntimeError('UI controls missing')
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
