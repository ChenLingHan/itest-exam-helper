# Build both executables against the same bundled dependencies.
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = [('ui', 'ui'), ('assets', 'assets'), ('model', 'model'),
         ('lib/ffmpeg.exe', 'lib'), ('LICENSE', '.'), ('LICENSE-MIT', '.'), ('MIT-LICENSE-SCOPE.md', '.'),
         ('THIRD_PARTY_NOTICES.md', '.'), ('config.example.yml', '.')]
binaries = []
# Selenium 4.51 exposes drivers through importlib-based lazy imports.
# Include every webdriver module and the native Selenium Manager explicitly.
hiddenimports = ['webview.platforms.edgechromium', 'webview.platforms.winforms'] + collect_submodules('selenium')
datas += collect_data_files('selenium', includes=['webdriver/remote/*.js', 'webdriver/common/*NOTICES*'])
from pathlib import Path
import selenium
manager = Path(selenium.__file__).parent / 'webdriver/common/windows/selenium-manager.exe'
binaries.append((str(manager), 'selenium/webdriver/common/windows'))
for package in ('vosk', 'webview', 'clr_loader', 'pythonnet'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(['gui.py', 'gui_worker.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports + ['openai', 'exam_runner', 'yaml', 'parsel', 'selenium'],
             hookspath=[], runtime_hooks=[], excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'])
pyz = PYZ(a.pure)
hooks = [s for s in a.scripts if s[0] not in ('gui', 'gui_worker')]
gui = EXE(pyz, hooks + [s for s in a.scripts if s[0] == 'gui'],
          [], exclude_binaries=True, name='iTEST', console=False, icon='assets/itest.ico')
worker = EXE(pyz, hooks + [s for s in a.scripts if s[0] == 'gui_worker'],
             [], exclude_binaries=True, name='iTEST-worker', console=True, icon='assets/itest.ico')
coll = COLLECT(gui, worker, a.binaries, a.datas, name='iTEST')
