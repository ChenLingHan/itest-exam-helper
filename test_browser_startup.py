import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import io
import zipfile
import unittest
from unittest.mock import MagicMock,patch
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from browser_startup import resolve_edge,start_edge,download_official_driver,BrowserStartError


class BrowserStartupTests(unittest.TestCase):
    def test_official_zip_retry_checks_version_and_caches_driver(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive: archive.writestr('msedgedriver.exe',b'MZ-test-only')
        response=MagicMock();response.status_code=200;response.__enter__.return_value=response
        response.iter_content.return_value=[buffer.getvalue()]
        version='156.0.4314.50'
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'SE_CACHE_PATH':folder}),patch('browser_startup.requests.get',return_value=response) as get,patch('browser_startup.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout=b'MSEdgeDriver 156.0.4314.50')):
            download_official_driver(f'https://msedgedriver.microsoft.com/{version}/edgedriver_win64.zip',version)
            self.assertEqual(Path(folder,'msedgedriver','win64',version,'msedgedriver.exe').read_bytes(),b'MZ-test-only')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
        with self.assertRaises(BrowserStartError):
            download_official_driver('https://example.com/driver.zip',version)

    def test_download_decode_failure_retries_then_resolves_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            browser=Path(folder,'msedge.exe');browser.touch()
            driver=Path(folder,'msedgedriver.exe');driver.touch()
            failure=types.SimpleNamespace(returncode=65,stdout=json.dumps({'result':{'message':'error decoding response body for url (https://msedgedriver.microsoft.com/156.0.4314.50/edgedriver_win64.zip)'}}).encode())
            success=types.SimpleNamespace(returncode=0,stdout=json.dumps({'result':{'browser_path':str(browser),'driver_path':str(driver)}}).encode())
            with patch('browser_startup.SeleniumManager._get_binary',return_value=Path('manager.exe')),patch('browser_startup.subprocess.run',side_effect=[failure,success]) as run,patch('browser_startup.download_official_driver') as download:
                self.assertEqual(resolve_edge(webdriver.EdgeOptions()),(str(browser),str(driver)))
                download.assert_called_once()
                self.assertIn('--offline',run.call_args.args[0])

    def test_driver_lookup_has_bounded_time_and_returns_explicit_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            browser=Path(folder,'msedge.exe');browser.touch()
            driver=Path(folder,'msedgedriver.exe');driver.touch()
            result=types.SimpleNamespace(returncode=0,stdout=json.dumps({'result':{'browser_path':str(browser),'driver_path':str(driver),'code':0}}).encode())
            with patch('browser_startup.SeleniumManager._get_binary',return_value=Path(folder,'manager.exe')),patch('browser_startup.subprocess.run',return_value=result) as run:
                self.assertEqual(resolve_edge(webdriver.EdgeOptions()),(str(browser),str(driver)))
                self.assertEqual(run.call_args.kwargs['timeout'],45)
                self.assertIn('--avoid-browser-download',run.call_args.args[0])
                self.assertIn('25',run.call_args.args[0])

    def test_download_timeout_is_distinct_from_login_failure(self):
        with patch('browser_startup.SeleniumManager._get_binary',return_value=Path('manager.exe')),patch('browser_startup.subprocess.run',side_effect=subprocess.TimeoutExpired('manager',45)):
            with self.assertRaisesRegex(BrowserStartError,'驱动超时'):
                resolve_edge(webdriver.EdgeOptions())

    def test_raw_manager_output_never_exposes_proxy_credentials(self):
        output=json.dumps({'result':{'code':65,'message':'http://user:private-proxy-password@proxy.invalid'}}).encode()
        with patch('browser_startup.SeleniumManager._get_binary',return_value=Path('manager.exe')),patch('browser_startup.subprocess.run',return_value=types.SimpleNamespace(returncode=65,stdout=output)):
            with self.assertRaises(BrowserStartError) as raised: resolve_edge(webdriver.EdgeOptions())
            self.assertNotIn('private-proxy-password',str(raised.exception))
            self.assertIn('驱动',str(raised.exception))

    def test_local_driver_connection_bypasses_proxy_without_changing_environment(self):
        driver=MagicMock()
        with patch.dict(os.environ,{'HTTP_PROXY':'http://proxy.invalid:8080'}),patch('browser_startup.resolve_edge',return_value=('edge.exe','driver.exe')),patch('browser_startup.webdriver.Edge',return_value=driver) as edge:
            self.assertIs(start_edge(),driver)
            options=edge.call_args.kwargs['options']
            self.assertTrue(options._ignore_local_proxy)
            self.assertEqual(options.binary_location,'edge.exe')
            self.assertEqual(os.environ['HTTP_PROXY'],'http://proxy.invalid:8080')

    def test_incompatible_driver_error_is_specific_and_service_is_stopped(self):
        service=MagicMock()
        with patch('browser_startup.resolve_edge',return_value=('edge.exe','driver.exe')),patch('browser_startup.Service',return_value=service),patch('browser_startup.webdriver.Edge',side_effect=SessionNotCreatedException('raw diagnostic')):
            with self.assertRaisesRegex(BrowserStartError,'浏览器会话'): start_edge()
            service.stop.assert_called_once()

    def test_invalid_manager_response_is_not_treated_as_browser_ready(self):
        with patch('browser_startup.SeleniumManager._get_binary',return_value=Path('manager.exe')),patch('browser_startup.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout=b'invalid')):
            with self.assertRaisesRegex(BrowserStartError,'有效结果'): resolve_edge(webdriver.EdgeOptions())


if __name__=='__main__': unittest.main()
