# SPDX-License-Identifier: MIT
import copy
import base64
import hashlib
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from app_updates import API_URL, PROJECT_URL, UpdateManager, release_info, stable_version, start_installer_after_exit
from desktop_bridge import Bridge

PAYLOAD=b'MZ'+b'example-installer'*200
FILENAME='iTEST-Exam-Helper-99.0.0-windows-x64-setup.exe'
URL=PROJECT_URL+'/releases/download/v99.0.0/'+FILENAME


def release(digest=True):
    asset={'name':FILENAME,'size':len(PAYLOAD),'browser_download_url':URL}
    if digest:asset['digest']='sha256:'+hashlib.sha256(PAYLOAD).hexdigest()
    return {'tag_name':'v99.0.0','draft':False,'prerelease':False,'body':'Example release',
            'assets':[asset,{'name':'SHA256SUMS.txt','browser_download_url':PROJECT_URL+'/releases/download/v99.0.0/SHA256SUMS.txt'}]}


class Response:
    def __init__(self,data=None,content=b'',gate=None):self.data=data;self.content=content;self.gate=gate
    def raise_for_status(self):pass
    def json(self):return self.data
    def close(self):pass
    def iter_content(self,size):
        if self.gate:self.gate.wait(2)
        for index in range(0,len(self.content),size):yield self.content[index:index+size]


class Session:
    def __init__(self,metadata=None,payload=PAYLOAD,gate=None):self.headers={};self.calls=[];self.metadata=metadata or release();self.payload=payload;self.gate=gate
    def get(self,url,**kwargs):
        self.calls.append(url)
        if url==API_URL:return Response(data=self.metadata)
        if url.endswith('SHA256SUMS.txt'):return Response(content=(hashlib.sha256(PAYLOAD).hexdigest()+'  '+FILENAME+'\n').encode())
        return Response(content=self.payload,gate=self.gate)


def wait(manager,*statuses):
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        if manager.snapshot()['status'] in statuses:return manager.snapshot()
        time.sleep(.01)
    raise AssertionError(manager.snapshot())


class UpdateTests(unittest.TestCase):
    def test_installer_handoff_waits_checks_hash_and_quotes_paths(self):
        with patch('app_updates.subprocess.Popen') as launch:
            start_installer_after_exit(Path(r"C:\App Data\a'b\setup.exe"),'a'*64)
            command=launch.call_args.args[0]
            script=base64.b64decode(command[-1]).decode('utf-16-le')
            self.assertIn('WaitForExit(30000)',script)
            self.assertIn("a''b",script)
            self.assertIn("'"+'a'*64+"'",script)
            self.assertLess(script.index('Get-FileHash'),script.index('Start-Process'))
    def test_only_stable_owned_installer_and_bounded_size(self):
        self.assertGreater(stable_version('v1.10.0'),stable_version('1.2.0'))
        for change in [{'prerelease':True},{'draft':True},{'tag_name':'v1.2.0-beta.1'}]:
            data=release();data.update(change)
            with self.assertRaises(ValueError):release_info(data)
        for url in ['https://example.com/setup.exe',URL+'?key=x',URL.replace('github.com','github.com.evil.test'),URL.replace('ChenLingHan','someone'),URL.replace('/releases/','/../releases/')]:
            data=release();data['assets'][0]['browser_download_url']=url
            with self.assertRaises(ValueError):release_info(data)
        data=release();data['assets'][0]['size']=2**31
        with self.assertRaises(ValueError):release_info(data)

    def test_manual_check_does_not_download_or_execute(self):
        with tempfile.TemporaryDirectory() as folder,patch('subprocess.Popen') as launch:
            session=Session();manager=UpdateManager(folder,session=session)
            self.assertTrue(manager.check());wait(manager,'available')
            self.assertEqual(session.calls,[API_URL]);launch.assert_not_called()
            self.assertEqual(manager.snapshot()['latest'],'99.0.0')

    def test_auto_download_verifies_reuses_cache_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as folder,patch('subprocess.Popen') as launch:
            session=Session();manager=UpdateManager(folder,session=session)
            manager.check(automatic=True);wait(manager,'ready')
            self.assertEqual(manager.installer_path().read_bytes(),PAYLOAD);launch.assert_not_called()
            manager.check();wait(manager,'available');manager.download();wait(manager,'ready')
            self.assertEqual(session.calls.count(URL),1)
            manager.installer_path().write_bytes(b'corrupt')
            with self.assertRaises(ValueError):manager.installer_path()

    def test_bad_hash_and_truncated_download_never_become_installable(self):
        for payload in [b'bad',b'X'*len(PAYLOAD),PAYLOAD+b'oversized']:
            with self.subTest(size=len(payload)),tempfile.TemporaryDirectory() as folder:
                manager=UpdateManager(folder,session=Session(payload=payload));manager.check(automatic=True);wait(manager,'error')
                with self.assertRaises(ValueError):manager.installer_path()
                self.assertFalse(list(Path(folder).rglob('*.part')))

    def test_cancel_and_checksum_manifest_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            gate=threading.Event();manager=UpdateManager(folder,session=Session(gate=gate));manager.check();wait(manager,'available');manager.download();manager.cancel_download();gate.set();wait(manager,'available')
            self.assertFalse(list(Path(folder).rglob('*.part')))
        with tempfile.TemporaryDirectory() as folder:
            manager=UpdateManager(folder,session=Session(metadata=release(False)));manager.check(automatic=True);wait(manager,'ready');self.assertTrue(manager.installer_path().is_file())

    def test_preference_persists_and_no_newer_release_is_reported_correctly(self):
        with tempfile.TemporaryDirectory() as folder:
            data=release();data['tag_name']='v0.0.1';manager=UpdateManager(folder,session=Session(metadata=data));manager.set_automatic(False)
            self.assertFalse(UpdateManager(folder).snapshot()['automatic'])
            manager.check();wait(manager,'current');self.assertFalse(manager.download())

    def test_install_requires_explicit_confirmation_and_idle_app(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);bridge._updater=UpdateManager(folder,bridge._update_event,Session());bridge._updater.check(automatic=True);wait(bridge._updater,'ready')
            bridge._state['busy']=True;self.assertFalse(bridge.install_update()['ok']);bridge._state['busy']=False
            started=threading.Event()
            with patch('desktop_bridge.subprocess.Popen',side_effect=lambda *a,**k:started.set()) as launch,patch.object(bridge,'_destroy_window'):
                self.assertTrue(bridge.install_update()['ok']);launch.assert_not_called()
                notice=bridge.get_state()['notice'];self.assertTrue(notice['confirm'])
                bridge.dispatch({'action':'confirm','id':notice['id']})
                self.assertTrue(started.wait(2));self.assertEqual(launch.call_count,1)


if __name__=='__main__':unittest.main()
