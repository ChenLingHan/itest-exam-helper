"""Bounded driver discovery with stage messages and credential-free errors."""
import json
import logging
import os
from pathlib import Path
import io
import re
import subprocess
import time
import uuid
import warnings
import zipfile
import requests
from selenium import webdriver
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.edge.service import Service
from selenium.common.exceptions import SessionNotCreatedException
from exam_schema import SchemaError

LOG=logging.getLogger('exam_runner')


class BrowserStartError(SchemaError):
    pass


def download_official_driver(url,version):
    """Retry only the exact Microsoft URL reported for the detected Edge build."""
    if not re.fullmatch(r'\d+(?:\.\d+){3}',version) or url!=f'https://msedgedriver.microsoft.com/{version}/edgedriver_win64.zip':
        raise BrowserStartError('驱动下载地址不符合微软官方格式，已停止。')
    LOG.info('驱动下载重试：正在从微软官方下载匹配版本，最多约 60 秒…')
    deadline=time.monotonic()+40
    try:
        with requests.get(url,stream=True,timeout=(10,20),allow_redirects=False) as response:
            if response.status_code!=200: raise ValueError('download status')
            content=bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content)>64*1024*1024 or time.monotonic()>deadline: raise ValueError('download limit')
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            member=archive.getinfo('msedgedriver.exe')
            if not 0<member.file_size<128*1024*1024: raise ValueError('invalid driver size')
            binary=archive.read(member)
        if not binary.startswith(b'MZ'): raise ValueError('invalid executable')
        cache=Path(os.environ.get('SE_CACHE_PATH',str(Path.home()/'.cache/selenium')))
        target=cache/'msedgedriver'/'win64'/version/'msedgedriver.exe'
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name('download-'+uuid.uuid4().hex+'.exe')
        try:
            temporary.write_bytes(binary)
            checked=subprocess.run([str(temporary),'--version'],capture_output=True,timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            found=re.search(r'\d+(?:\.\d+){3}',checked.stdout.decode('utf-8',errors='replace'))
            if checked.returncode or not found or found[0].split('.')[:3]!=version.split('.')[:3]:
                raise ValueError('driver version mismatch')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    except Exception as error:
        raise BrowserStartError('微软官方驱动下载重试未完成。请检查网络下载或系统程序拦截提示，然后重试“检查浏览器”。') from error
    LOG.info('微软官方驱动下载完成，版本校验通过。')


def resolve_edge(options):
    LOG.info('浏览器启动 1/3：检查 Edge 并匹配驱动；首次使用需要联网下载，常规准备最多等待 45 秒。')
    try:
        manager=SeleniumManager._get_binary()
    except Exception as error:
        raise BrowserStartError('安装包中的驱动管理器缺失，请重新安装最新版本。') from error
    args=[str(manager),'--browser','edge','--language-binding','python','--output','json',
          '--timeout','25','--avoid-browser-download','--avoid-stats','--skip-driver-in-path']
    if options.binary_location:
        args.extend(['--browser-path',options.binary_location])
    try:
        result=subprocess.run(args,capture_output=True,timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired as error:
        raise BrowserStartError('匹配或下载 Edge 驱动超时，浏览器尚未启动。请检查网络是否允许下载 Edge 驱动，然后重试。') from error
    except PermissionError as error:
        raise BrowserStartError('驱动管理器无法执行，请检查 Windows 的拦截提示或重新安装程序。') from error
    except OSError as error:
        raise BrowserStartError('驱动管理器无法启动，请重新安装程序后重试。') from error
    try:
        output=json.loads(result.stdout.decode('utf-8-sig'))
        data=output['result']
        if not isinstance(data,dict): raise ValueError()
    except (ValueError,KeyError,TypeError,UnicodeError) as error:
        raise BrowserStartError('驱动管理器未返回有效结果，请重新安装程序后重试。') from error
    if result.returncode or data.get('code',0):
        download=re.search(r'https://msedgedriver\.microsoft\.com/(\d+(?:\.\d+){3})/edgedriver_win64\.zip',str(data.get('message','')))
        if download and os.name=='nt':
            download_official_driver(download[0],download[1])
            try:
                retry=subprocess.run(args+['--offline'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
                parsed=json.loads(retry.stdout.decode('utf-8-sig'))['result']
                if retry.returncode or parsed.get('code',0): raise ValueError()
                data=parsed
            except Exception as error:
                raise BrowserStartError('驱动已下载，但无法匹配当前 Edge。请更新 Edge 后重试。') from error
        else:
            # Never expose raw Manager output; it may include proxy credentials.
            raise BrowserStartError('无法找到或下载匹配的 Edge 驱动。请确认已安装 Edge，且网络允许下载驱动；能浏览网页不代表驱动下载地址可达。')
    browser=data.get('browser_path');driver=data.get('driver_path')
    if not isinstance(browser,str) or not browser or not Path(browser).is_file():
        raise BrowserStartError('没有检测到可用的 Microsoft Edge，请安装或修复 Edge 后重试。')
    if not isinstance(driver,str) or not driver or not Path(driver).is_file():
        raise BrowserStartError('没有获得可用的 Edge 驱动，请检查驱动下载是否被网络或系统拦截。')
    LOG.info('浏览器启动 2/3：驱动已就绪，正在打开 Edge…')
    return browser,driver


def start_edge(headless=False):
    options=webdriver.EdgeOptions()
    if headless: options.add_argument('--headless=new')
    options.add_argument('--window-size=1440,1000')
    options.add_argument('--disable-features=msImportBrowserData')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    # The local driver control connection must not be routed through HTTP_PROXY.
    # This does not change browser traffic, driver downloads, or model API traffic.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning)
        options.ignore_local_proxy_environment_variables()
    browser,driver_path=resolve_edge(options)
    options.binary_location=browser
    service=Service(driver_path)
    try:
        driver=webdriver.Edge(service=service,options=options)
    except SessionNotCreatedException as error:
        service.stop()
        raise BrowserStartError('Edge 未能创建浏览器会话。请先更新 Edge，再重新获取匹配驱动；若仍失败，请查看系统的程序拦截提示。') from error
    except Exception as error:
        service.stop()
        raise BrowserStartError('驱动已找到，但 Edge 启动失败。请查看系统拦截提示，更新或修复 Edge 后重试。') from error
    LOG.info('浏览器启动 3/3：Edge 已打开。')
    return driver
