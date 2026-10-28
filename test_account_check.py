import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from desktop_bridge import Bridge
from gui_worker import check_account
from gui import initial_window_size


class AccountCheckTests(unittest.TestCase):
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
