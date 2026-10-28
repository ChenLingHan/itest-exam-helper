"""真实窗口关闭回调的离线回归检查，不连接考试网站。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import webview
from desktop_bridge import Bridge


def main():
    with tempfile.TemporaryDirectory() as folder:
        bridge=Bridge(folder)
        helper=subprocess.Popen([sys.executable,'-u','-c','import sys; sys.stdin.readline()'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        bridge._process=helper
        bridge._state['connected']=True
        window=webview.create_window('iTEST close regression',html='<html><body>offline</body></html>',hidden=True)
        bridge._window=window
        window.events.closing+=bridge._on_closing
        passed=threading.Event()
        def check():
            window.events.loaded.wait(15)
            window.destroy()
            if window.events.closed.wait(5) and helper.poll()==0:
                passed.set()
                print('Real WebView2 close callback and idle worker shutdown OK',flush=True)
        def watchdog():
            if not passed.wait(20):
                if helper.poll() is None: helper.kill()
                print('Close regression timed out',flush=True)
                os._exit(1)
        threading.Thread(target=watchdog,daemon=True).start()
        webview.start(check,gui='edgechromium',private_mode=True)
        return 0 if passed.wait(2) else 1


if __name__=='__main__': raise SystemExit(main())
