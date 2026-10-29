# SPDX-License-Identifier: MIT
"""Public stable-release updates. Downloads are verified before explicit installation."""
import copy
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests
from app_paths import VERSION

REPOSITORY = 'ChenLingHan/itest-exam-helper'
PROJECT_URL = 'https://github.com/' + REPOSITORY
WEBSITE_URL = 'https://chenlinghan.github.io/itest-exam-helper/'
API_URL = 'https://api.github.com/repos/' + REPOSITORY + '/releases/latest'
MAX_INSTALLER = 512 * 1024 * 1024


def stable_version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
    if not match:
        raise ValueError('更新版本格式无效。')
    return tuple(map(int, match.groups()))


def trusted_download(url, tag, filename):
    parsed = urlparse(str(url))
    return (parsed.scheme == 'https' and parsed.hostname == 'github.com'
            and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and parsed.path.lower() == f'/{REPOSITORY}/releases/download/{tag}/{filename}'.lower())


def release_info(data):
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        raise ValueError('仅接收正式发布的稳定版本。')
    tag = data.get('tag_name', '')
    stable_version(tag)
    version = tag.removeprefix('v')
    filename = f'iTEST-Exam-Helper-{version}-windows-x64-setup.exe'
    asset = next((a for a in data.get('assets', []) if a.get('name') == filename), None)
    if not asset or not isinstance(asset.get('size'), int) or not 0 < asset['size'] <= MAX_INSTALLER:
        raise ValueError('新版 Windows 安装包尚未准备好，请稍后重试。')
    if not trusted_download(asset.get('browser_download_url'), tag, filename):
        raise ValueError('更新下载地址不属于本项目。')
    digest = asset.get('digest', '') or ''
    checksum_url = None
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
        checksum = next((a for a in data.get('assets', []) if a.get('name') == 'SHA256SUMS.txt'), None)
        if not checksum or not trusted_download(checksum.get('browser_download_url'), tag, 'SHA256SUMS.txt'):
            raise ValueError('新版缺少有效校验信息，暂不下载。')
        checksum_url = checksum['browser_download_url']
        digest = ''
    return {'version': version, 'filename': filename, 'size': asset['size'],
            'url': asset['browser_download_url'], 'sha256': digest.removeprefix('sha256:').lower(),
            'checksum_url': checksum_url, 'release_url': PROJECT_URL + '/releases/tag/' + tag,
            'notes': str(data.get('body') or '')[:10000]}


class UpdateCancelled(Exception):
    pass


class UpdateManager:
    def __init__(self, root, listener=lambda state: None, session=None):
        self.root = Path(root) / '.updates'
        self.settings_path = Path(root) / 'update_settings.json'
        self.listener = listener
        self.session = session or requests.Session()
        self.session.headers.update({'Accept': 'application/vnd.github+json', 'User-Agent': 'itest-exam-helper/' + VERSION})
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.cancel_event = threading.Event()
        self.monitor = None
        self.downloaded = None
        self.release = None
        self.auto = True
        self.last_check = 0
        try:
            saved = json.loads(self.settings_path.read_text(encoding='utf-8'))
            self.auto = saved.get('automatic', True) is True
            self.last_check = min(float(saved.get('last_check', 0)), time.time())
        except (OSError, ValueError, TypeError):
            pass
        self.state = {'status': 'idle', 'current': VERSION, 'latest': None, 'automatic': self.auto,
                      'progress': None, 'received': 0, 'size': 0, 'message': '安装前会请你确认', 'notes': ''}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def _publish(self, **values):
        with self.lock:
            self.state.update(values)
            snapshot = copy.deepcopy(self.state)
        # Never call a Bridge listener while holding the update lock.
        self.listener(snapshot)

    def _save_preferences(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.settings_path.with_suffix('.json.tmp')
        temp.write_text(json.dumps({'automatic': self.auto, 'last_check': self.last_check}), encoding='utf-8')
        temp.replace(self.settings_path)

    def set_automatic(self, enabled):
        with self.lock:
            previous=self.auto
            self.auto = bool(enabled)
            try:
                self._save_preferences()
            except OSError:
                self.auto=previous
                raise
        self._publish(automatic=self.auto)

    def start_monitor(self):
        with self.lock:
            if self.monitor and self.monitor.is_alive():
                return
            def monitor():
                while not self.stop_event.is_set():
                    cached=self.state['status']=='idle' and any(self.root.glob('*.exe'))
                    if self.auto and self.state['status']!='ready' and (cached or time.time() - self.last_check >= 86400):
                        self.check(automatic=True)
                    self.stop_event.wait(900)
            self.monitor = threading.Thread(target=monitor, daemon=True)
            self.monitor.start()

    def check(self, automatic=False):
        with self.lock:
            if self.state['status'] in ('checking', 'downloading', 'installing'):
                return False
            self.state['status'] = 'checking'
        self._publish(status='checking', message='正在检查新版本…', progress=None)
        threading.Thread(target=self._check, args=(automatic,), daemon=True).start()
        return True

    def _check(self, automatic):
        try:
            response = self.session.get(API_URL, timeout=(8, 20))
            response.raise_for_status()
            data = response.json()
            if data.get('draft') or data.get('prerelease'):
                raise ValueError('暂时没有可用的正式更新。')
            newer = stable_version(data.get('tag_name')) > stable_version(VERSION)
            info = release_info(data) if newer else None
            with self.lock:
                self.release = info
                self.last_check = time.time()
                self._save_preferences()
            self._publish(status='available' if newer else 'current', latest=data['tag_name'].removeprefix('v'),
                          notes=info['notes'] if info else '', size=info['size'] if info else 0,
                          message='发现新版本，可以下载' if newer else '已是最新正式版')
            if newer and automatic and self.auto and not self.stop_event.is_set():
                self.download()
        except Exception as error:
            # Do not retry every polling tick or show network internals/credentials.
            with self.lock:
                self.last_check = time.time()
            message = str(error) if isinstance(error, ValueError) else '检查更新失败，请检查网络后重试。'
            self._publish(status='error', message=message)

    def download(self):
        with self.lock:
            if not self.release or self.state['status'] in ('checking', 'downloading', 'installing'):
                return False
            info = copy.deepcopy(self.release)
            self.cancel_event.clear()
            self.state['status'] = 'downloading'
        self._publish(status='downloading', message='正在下载更新…', received=0, progress=0)
        threading.Thread(target=self._download, args=(info,), daemon=True).start()
        return True

    def _expected_hash(self, info):
        if info['sha256']:
            return info['sha256']
        response = self.session.get(info['checksum_url'], timeout=(8, 20), stream=True)
        try:
            response.raise_for_status()
            content = b''
            for chunk in response.iter_content(2048):
                content += chunk
                if len(content) > 16384:
                    raise ValueError('更新校验文件异常。')
            for line in content.decode('ascii').splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip('*') == info['filename'] and re.fullmatch('[0-9a-fA-F]{64}', parts[0]):
                    return parts[0].lower()
            raise ValueError('没有找到安装包的校验值。')
        finally:
            response.close()

    def _download(self, info):
        partial = self.root / (info['filename'] + '.part')
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            expected = self._expected_hash(info)
            target = self.root / info['filename']
            if target.is_file() and target.stat().st_size==info['size'] and file_hash(target)==expected:
                with self.lock:self.downloaded=(target,expected,info['size'])
                self._publish(status='ready',message='更新已下载并通过校验，安装前请结束当前任务',progress=100,received=info['size'])
                return
            response = self.session.get(info['url'], timeout=(8, 35), stream=True)
            try:
                response.raise_for_status()
                received, last_update = 0, 0
                digest = hashlib.sha256()
                with partial.open('wb') as output:
                    for chunk in response.iter_content(256 * 1024):
                        if self.cancel_event.is_set() or self.stop_event.is_set():
                            raise UpdateCancelled()
                        if not chunk:
                            continue
                        received += len(chunk)
                        if received > info['size']:
                            raise ValueError('安装包大小异常，下载已停止。')
                        output.write(chunk)
                        digest.update(chunk)
                        if time.monotonic() - last_update > .2:
                            last_update = time.monotonic()
                            self._publish(received=received, progress=min(99, int(received * 100 / info['size'])))
                if received != info['size'] or digest.hexdigest() != expected:
                    raise ValueError('安装包校验未通过，请重新下载。')
                if self.cancel_event.is_set() or self.stop_event.is_set():
                    raise UpdateCancelled()
                partial.replace(target)
                with self.lock:
                    self.downloaded = (target, expected, info['size'])
                self._publish(status='ready', message='更新已下载并通过校验，安装前请结束当前任务', progress=100, received=received)
            finally:
                response.close()
        except UpdateCancelled:
            partial.unlink(missing_ok=True)
            self._publish(status='available', message='下载已取消，可稍后重试', progress=None)
        except Exception as error:
            partial.unlink(missing_ok=True)
            message = str(error) if isinstance(error, ValueError) else '下载更新失败，请检查网络后重试。'
            self._publish(status='error', message=message, progress=None)

    def cancel_download(self):
        self.cancel_event.set()
        if self.snapshot()['status']=='downloading':self._publish(message='正在取消下载…')

    def invalidate_download(self):
        with self.lock:self.downloaded=None
        self._publish(status='error',message='更新校验或安装启动失败，请重新下载。',progress=None)

    def begin_install(self):
        with self.lock:
            if self.state['status']!='ready' or not self.downloaded:return False
            self.state['status']='installing'
        self._publish(status='installing',message='正在准备安装，当前窗口即将关闭…')
        return True

    def installer_path(self):
        with self.lock:
            downloaded = self.downloaded
        if not downloaded:
            raise ValueError('请先下载并校验更新。')
        path, expected, size = downloaded
        if not path.is_file() or path.stat().st_size != size or file_hash(path) != expected:
            raise ValueError('更新文件已变化，请重新下载。')
        if path.resolve().parent != self.root.resolve():
            raise ValueError('安装包位置无效。')
        return path

    def installation(self):
        path=self.installer_path()
        with self.lock:return path,self.downloaded[1]

    def close(self):
        self.stop_event.set()
        self.cancel_event.set()


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def start_installer_after_exit(path, digest):
    """A system helper waits for this process, rechecks the hash, then opens Setup."""
    if os.name!='nt' or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('此安装包仅支持 Windows。')
    literal=str(path).replace("'","''")
    directory=str(Path(path).parent).replace("'","''")
    script=("$ErrorActionPreference='Stop';"
            f"$updateParent=Get-Process -Id {os.getpid()} -ErrorAction SilentlyContinue;"
            "if($updateParent -and -not $updateParent.WaitForExit(30000)){exit 1};"
            f"$updateInstaller='{literal}';"
            f"if((Get-FileHash -LiteralPath $updateInstaller -Algorithm SHA256).Hash.ToLowerInvariant() -ne '{digest}'){{exit 2}};"
            f"Start-Process -FilePath $updateInstaller -WorkingDirectory '{directory}' -WindowStyle Normal")
    encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    powershell=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    subprocess.Popen([str(powershell),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                     cwd=str(Path(path).parent),creationflags=subprocess.CREATE_NO_WINDOW)
