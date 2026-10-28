"""不连接网站、不调用模型的界面与工作流检查。"""
import io
import json
import logging
from pathlib import Path
import tempfile
import subprocess
import threading
import types
import unittest
from unittest.mock import MagicMock, patch

import gui
from desktop_bridge import Bridge
import gui_worker


class ConfigTests(unittest.TestCase):
    def test_delay_and_required_ai(self):
        config = {"username": "test", "password": "test", "sleep_time": 0}
        gui.validate_config(config)
        for delay in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                gui.validate_config({**config, "sleep_time": delay})
        with self.assertRaises(ValueError):
            gui.validate_config(config, need_ai=True)


class WorkerTests(unittest.TestCase):
    def workflow(self, auto_submit, fail=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = MagicMock()
            runner.config = {"password": "private-password", "ai": {"apikey": "private-api-key"}}
            runner.cache = root
            runner.driver.page_source = "<html>fake</html>"
            runner.driver.current_window_handle = "exam"
            runner.driver.window_handles = ["list", "exam"]
            runner.list_window = "list"
            runner.papers.return_value = [{"ksdId": "123", "ksName": "示例听力"}]
            runner.submit.return_value = [{"ksdId":"123", "ksName":"示例听力", "canKaoshiJudgeBean":{"kaoshiBtnInfo":"已交卷"}}, {"ksdId":"456", "ksName":"下一张试卷"}]
            solver = MagicMock()
            solver.prepare.return_value = [{"id": "q1", "value": "A"}]
            if fail:
                solver.prepare.side_effect = ValueError("private-api-key invalid")
            module = types.SimpleNamespace(ROOT=root, ExamRunner=MagicMock(return_value=runner), ListeningSolver=MagicMock(return_value=solver), parse_groups=MagicMock(return_value=[]))
            commands = [{"action": "load", "config": runner.config}, {"action": "run", "index": 0, "exam_code": "123456", "auto_submit": auto_submit}, {"action": "close"}]
            output = io.StringIO()
            handlers = logging.getLogger().handlers[:]
            try:
                with patch.dict("sys.modules", {"exam_runner": module}), patch("sys.stdin", io.StringIO("\n".join(json.dumps(item) for item in commands))), patch("sys.stdout", output):
                    gui_worker.main()
            finally:
                for handler in logging.getLogger().handlers[:]:
                    if handler not in handlers:
                        logging.getLogger().removeHandler(handler)
                        handler.close()
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            runner.enter.assert_called_once_with(runner.papers.return_value[0], exam_code="123456")
            runner.driver.quit.assert_called_once()
            return runner, events

    def test_review_mode_does_not_submit(self):
        runner, events = self.workflow(False)
        runner.fill.assert_called_once()
        runner.submit.assert_not_called()
        self.assertEqual(events[-1]["event"], "done")
        self.assertFalse(events[-1]["submitted"])
        self.assertEqual(events[-1]["papers"][0]["ksdId"], "123")
        runner.driver.switch_to.window.assert_any_call("exam")

    def test_explicit_auto_submit(self):
        runner, events = self.workflow(True)
        runner.submit.assert_called_once()
        self.assertTrue(events[-1]["submitted"])
        self.assertEqual(events[-1]['papers'],runner.submit.return_value)
        self.assertEqual(events[-1]['papers'][0]['canKaoshiJudgeBean']['kaoshiBtnInfo'],'已交卷')

    def test_failure_never_submits_or_exposes_key(self):
        runner, events = self.workflow(True, fail=True)
        runner.fill.assert_not_called()
        runner.submit.assert_not_called()
        self.assertEqual(events[-1]["event"], "error")
        self.assertNotIn("private-api-key", events[-1]["message"])


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.bridge = Bridge(self.folder.name)
        self.config = {'username': 'test', 'password': 'private-password', 'sleep_time': 1,
                       'ai': {'model': 'test', 'apikey': 'private-api-key', 'base_url': 'https://example.com/v1'}}
        self.bridge._config = self.config
        self.bridge._session = self.config.copy()
        self.process = MagicMock()
        self.process.poll.return_value = None
        self.bridge._process = self.process
        self.bridge._state.update(connected=True, papers=[{'ksdId': '123', 'ksName': '示例听力'}])

    def tearDown(self):
        self.folder.cleanup()

    def test_confirm_is_required_and_single_use(self):
        with patch.object(self.bridge, '_send') as send:
            state = self.bridge.dispatch({'action': 'run', 'index': 0, 'config': self.config})
            send.assert_not_called()
            self.assertTrue(state['notice']['confirm'])
            request = {'action': 'confirm', 'id': state['notice']['id']}
            self.bridge.dispatch(request)
            self.bridge.dispatch(request)
            send.assert_called_once()
            self.assertFalse(send.call_args.args[0]['auto_submit'])

    def test_stale_confirmation_and_cancel_cannot_start(self):
        with patch.object(self.bridge, '_send') as send:
            state = self.bridge.dispatch({'action': 'run', 'index': 0})
            self.bridge.dispatch({'action': 'dismiss'})
            self.bridge.dispatch({'action': 'confirm', 'id': state['notice']['id']})
            send.assert_not_called()

    def test_public_state_does_not_expose_secrets(self):
        self.bridge._event(self.process, {'event': 'log', 'message': 'private-password private-api-key'})
        state = json.dumps(self.bridge.get_state())
        self.assertNotIn('private-password', state)
        self.assertNotIn('private-api-key', state)

    def test_stop_and_close_are_inline(self):
        self.bridge._state["busy"] = True
        self.assertFalse(self.bridge._on_closing())
        state = self.bridge.get_state()
        self.assertTrue(state['notice']['confirm'])
        self.assertEqual(state['notice']['label'], '退出程序')

    def test_malformed_selection_and_missing_code_never_start(self):
        with patch.object(self.bridge, '_send') as send:
            for index in (True, -1, 9, '0'):
                state = self.bridge.dispatch({'action': 'run', 'index': index})
                self.assertTrue(state['notice']['error'])
            self.bridge._state['papers'][0]['examCodeFlag'] = True
            state = self.bridge.dispatch({'action': 'run', 'index': 0})
            self.assertIn('考试码', state['notice']['text'])
            send.assert_not_called()

    def test_busy_request_cannot_start_duplicate_job(self):
        self.bridge._state['busy'] = True
        with patch.object(self.bridge, '_send') as send:
            self.bridge.dispatch({'action': 'load', 'config': self.config})
            self.bridge.dispatch({'action': 'run', 'index': 0})
            send.assert_not_called()


    def test_idle_close_cleans_up_without_confirmation(self):
        self.bridge._window = MagicMock()
        closed = threading.Event()
        self.bridge._window.destroy.side_effect = closed.set
        self.assertFalse(self.bridge._on_closing())
        self.assertTrue(closed.wait(2), '空闲退出未完成')
        self.assertIsNone(self.bridge.get_state()['notice'])
        self.process.stdin.write.assert_called_once()

    def test_destroy_callback_does_not_deadlock(self):
        self.bridge._window = MagicMock()
        result = []
        def destroy():
            # 模拟窗口在另一条 UI 线程同步调用关闭回调。
            callback = threading.Thread(target=lambda: result.append(self.bridge._on_closing()),daemon=True)
            callback.start()
            callback.join(.5)
            if callback.is_alive(): raise AssertionError('关闭时仍然持锁，回调发生死锁')
        self.bridge._window.destroy.side_effect = destroy
        self.bridge._cleanup(self.process,True)
        self.assertEqual(result,[True])
        self.assertIsNone(self.bridge.get_state()['notice'])

    def test_stuck_idle_worker_has_bounded_fallback(self):
        self.process.wait.side_effect = [subprocess.TimeoutExpired('worker',2),0]
        self.bridge._window = MagicMock()
        with patch('desktop_bridge.subprocess.run') as kill:
            self.bridge._cleanup(self.process,True)
        self.assertIsNone(self.bridge._process)
        self.bridge._window.destroy.assert_called_once()
        if __import__('os').name=='nt':
            kill.assert_called_once()
            self.assertEqual(kill.call_args.args[0],['taskkill','/PID',str(self.process.pid),'/T','/F'])

    def test_done_refreshes_papers_and_allows_other_paper(self):
        from task_progress import TaskProgress
        self.bridge._task = TaskProgress(self.bridge._state['papers'][0],True)
        refreshed = [{'ksdId':'123','ksName':'示例听力','canKaoshiJudgeBean':{'kaoshiBtnInfo':'已交卷'}},
                     {'ksdId':'456','ksName':'下一张试卷'}]
        self.bridge._event(self.process,{'event':'done','submitted':True,'papers':refreshed})
        state=self.bridge.get_state()
        self.assertEqual(state['papers'],refreshed)
        self.assertFalse(state['completed'])
        self.assertIn('123',state['blocked_paper_ids'])
        with patch.object(self.bridge,'_send') as send:
            state=self.bridge.dispatch({'action':'run','index':0})
            self.assertTrue(state['notice']['error'])
            state=self.bridge.dispatch({'action':'run','index':1})
            self.assertTrue(state['notice']['confirm'])
            self.bridge.dispatch({'action':'confirm','id':state['notice']['id']})
            self.assertEqual(send.call_args.args[0]['index'],1)


if __name__ == '__main__':
    unittest.main()
