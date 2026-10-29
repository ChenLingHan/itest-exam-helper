import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from desktop_bridge import Bridge
from gui_worker import check_account
from gui import initial_window_size
from browser_startup import BrowserStartError


class AccountCheckTests(unittest.TestCase):
    def test_retry_clears_previous_worker_error(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);process=MagicMock();process.poll.return_value=None
            bridge._process=process;bridge._worker_failure_message='old failure'
            bridge._send({'action':'check_browser'})
            self.assertIsNone(bridge._worker_failure_message)

    def test_launch_failure_reports_os_reason_and_resets_both_checks(self):
        for browser_only in (True,False):
            for code,expected in ((2,'未找到后台'),(5,'系统拒绝'),(225,'安全软件'),(193,'运行库')):
                with self.subTest(browser_only=browser_only,code=code), tempfile.TemporaryDirectory() as folder:
                    bridge=Bridge(folder)
                    error=OSError(code,'unsaved-password private-key')
                    error.winerror=code
                    with patch('desktop_bridge.subprocess.Popen',side_effect=error):
                        result=bridge.start_account_test({'username':'tester','password':'unsaved-password'},browser_only)
                    self.assertFalse(result['ok'])
                    self.assertIn(expected,result['message'])
                    self.assertIn(str(code),result['message'])
                    self.assertFalse(bridge.get_state()['busy'])
                    self.assertFalse(bridge.get_state()['account_test']['busy'])
                    diagnostics=Path(folder,'.exam_work','startup.log').read_text(encoding='utf-8')
                    for secret in ('unsaved-password','private-key'):
                        self.assertNotIn(secret,json.dumps(bridge.get_state())+diagnostics)

    def test_broken_pipe_is_actionable_and_retry_is_not_busy(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);process=MagicMock();process.poll.return_value=None
            process.stdin.flush.side_effect=BrokenPipeError('unsaved-password')
            bridge._process=process
            result=bridge.start_browser_test()
            self.assertIn('通信中断',result['message'])
            self.assertFalse(bridge.get_state()['busy'])
            self.assertNotIn('unsaved-password',json.dumps(bridge.get_state()))

    def test_loader_exit_includes_code_and_does_not_discard_error(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);process=MagicMock()
            process.stdout=io.StringIO('[PYI] Failed to load Python DLL private-key\n')
            process.wait.return_value=0xc0000135
            bridge._process=process
            bridge._state['account_test']={'busy':True}
            bridge._state['busy']=True
            bridge._read(process)
            state=bridge.get_state()
            self.assertIn('运行库',state['account_test']['message'])
            self.assertIn('C0000135',state['status'])
            self.assertFalse(state['busy'])
            self.assertNotIn('private-key',json.dumps(state))
            self.assertIsNone(bridge._process)

    def test_worker_error_survives_following_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);process=MagicMock();bridge._process=process
            bridge._state['account_test']={'busy':True}
            bridge._event(process,{'event':'error','message':'后台启动失败：ModuleNotFoundError'})
            bridge._event(process,{'event':'exit','returncode':1})
            self.assertEqual(bridge.get_state()['account_test']['message'],'后台启动失败：ModuleNotFoundError')
            self.assertEqual(bridge.get_state()['status'],'后台启动失败：ModuleNotFoundError')

    def test_browser_check_needs_no_credentials_and_never_logs_in(self):
        runner=MagicMock();runner.driver.title='iTEST browser check'
        self.assertTrue(check_account({},lambda _:runner,browser_only=True)['ok'])
        runner.login.assert_not_called();runner.papers.assert_not_called();runner.enter.assert_not_called()
        runner.driver.quit.assert_called_once()

    def test_specific_browser_errors_reach_the_ui(self):
        runner=MagicMock();runner.start.side_effect=BrowserStartError('匹配 Edge 驱动超时')
        result=check_account({},lambda _:runner,browser_only=True)
        self.assertIn('驱动超时',result['message']);self.assertFalse(result['ok'])

    def test_success_with_empty_exam_list_does_not_enter_exam(self):
        runner=MagicMock();runner.papers.return_value=[]
        factory=MagicMock(return_value=runner)
        result=check_account({'username':'test-user','password':'private-pass'},factory)
        self.assertTrue(result['ok'])
        runner.login.assert_called_once_with(timeout=90)
        runner.enter.assert_not_called();runner.fill.assert_not_called();runner.submit.assert_not_called()
        runner.driver.quit.assert_called_once()

    def test_failure_cleans_up_and_never_echoes_credentials(self):
        runner=MagicMock();runner.login.side_effect=RuntimeError('private-pass request failed')
        result=check_account({'password':'private-pass'},lambda _:runner)
        self.assertFalse(result['ok']);self.assertNotIn('private-pass',json.dumps(result))
        runner.papers.assert_not_called();runner.enter.assert_not_called();runner.driver.quit.assert_called_once()

    def test_bridge_does_not_save_test_credentials_or_change_active_session(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);process=MagicMock();bridge._process=process
            original=bridge.get_config();bridge._session={'unchanged':True}
            with patch.object(bridge,'_send') as send:
                result=bridge.start_account_test({'username':'tester','password':'private-pass'})
                self.assertTrue(result['ok']);self.assertTrue(bridge.get_state()['busy'])
                self.assertFalse(bridge.get_state()['connected'])
                self.assertEqual(send.call_args.args[0]['action'],'check_login')
                self.assertNotIn('ai',send.call_args.args[0]['config'])
            self.assertFalse(Path(folder,'config.yml').exists())
            self.assertEqual(bridge.get_config(),original);self.assertEqual(bridge._session,{'unchanged':True})
            bridge._event(process,{'event':'account-test','request_id':'stale','ok':True,'message':'stale'})
            self.assertTrue(bridge.get_state()['busy'])
            bridge._event(process,{'event':'account-test','request_id':result['request_id'],'ok':True,'message':'登录测试通过'})
            state=bridge.get_state();self.assertFalse(state['busy']);self.assertTrue(state['account_test']['ok'])
            self.assertNotIn('private-pass',json.dumps(state))

    def test_account_test_rejects_missing_fields_and_existing_exam_tasks(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder)
            self.assertFalse(bridge.start_account_test({'username':'','password':''})['ok'])
            bridge._state['busy']=True
            self.assertFalse(bridge.start_account_test({'username':'a','password':'b'})['ok'])

    def test_window_size_fits_small_and_scaled_desktops(self):
        for width,height in ((1920,1040),(1366,728),(1024,640),(800,600),(640,480)):
            with self.subTest(screen=(width,height)):
                w,h,minimum=initial_window_size(width,height)
                self.assertLess(w,width);self.assertLess(h,height)
                self.assertLessEqual(minimum[0],w);self.assertLessEqual(minimum[1],h)
        self.assertEqual(initial_window_size(1920,1040)[:2],(1120,820))


if __name__=='__main__': unittest.main()
