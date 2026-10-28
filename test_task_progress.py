"""真实阶段计数和终态语义，全部离线。"""
import unittest
from task_progress import TaskProgress


class ProgressTests(unittest.TestCase):
    def task(self,submit=True):
        task=TaskProgress({'ksdId':'1','ksName':'示例听力'},submit,clock=lambda:100)
        task.consume('共 6 组、25 道题，需处理 33 份有效录音。')
        return task

    def test_transcription_start_is_not_completion(self):
        task=self.task()
        task.consume('录音下载 33/33')
        task.consume('正在转写录音 33/33...')
        state=task.snapshot()
        transcribe=state['stages'][2]
        self.assertEqual(transcribe['done'],32)
        self.assertEqual(transcribe['active'],33)
        self.assertLess(state['percent'],100)
        task.consume('录音转写完成 33/33')
        self.assertEqual(task.snapshot()['stages'][2]['done'],33)

    def test_stage_transition_preserves_finished_counts(self):
        task=self.task()
        task.consume('正在转写录音 17/33...')
        task.consume('听力转写完成，正在生成答案...')
        task.consume('答案生成 2/6 组，已通过题号和选项校验。')
        state=task.snapshot()
        self.assertEqual(state['stage'],'generate')
        self.assertEqual(state['stages'][2]['done'],33)
        self.assertEqual(state['stages'][3]['done'],2)

    def test_fill_needs_verification_and_submission_needs_done(self):
        task=self.task()
        task.consume('答案已填入 25/25')
        self.assertEqual(task.snapshot()['stages'][4]['state'],'running')
        task.consume('已核对 25 道题全部选中对应选项。')
        task.consume('答案核对完成，10.0 秒后交卷。')
        self.assertEqual(task.snapshot()['submit_at'],110)
        task.consume('已确认交卷，正在等待网站结果...')
        task.consume('网站已确认提交成功，接收 25 道题答案。')
        self.assertTrue(task.snapshot()['submitted'])
        self.assertLess(task.snapshot()['percent'],100)
        task.finish(True)
        self.assertEqual(task.snapshot()['percent'],100)
        self.assertEqual(task.snapshot()['status'],'submitted')

    def test_manual_review_is_not_submitted(self):
        task=self.task(False)
        task.finish(False)
        state=task.snapshot()
        self.assertEqual(state['percent'],100)
        self.assertEqual(state['status'],'review')
        self.assertFalse(state['submitted'])
        self.assertEqual(state['stages'][-1]['state'],'manual')
        self.assertEqual(state['total_steps'],5)
        self.assertIn('尚未交卷',state['detail'])

    def test_failure_and_unrelated_logs_do_not_claim_completion(self):
        task=self.task()
        task.consume('正在转写录音 5/33...')
        before=task.snapshot()['percent']
        task.consume('HTTP Request: POST https://example.com 200 OK')
        self.assertEqual(before,task.snapshot()['percent'])
        task.fail('模型超时')
        task.consume('录音转写完成 33/33')
        state=task.snapshot()
        self.assertEqual(state['stages'][2]['done'],4)
        self.assertEqual(state['stages'][2]['state'],'error')
        self.assertLess(state['percent'],100)

    def test_error_after_receipt_keeps_submission_fact(self):
        task=self.task()
        task.consume('网站已确认提交成功，接收 25 道题答案。')
        task.fail('列表刷新失败')
        self.assertTrue(task.snapshot()['submitted'])
        self.assertEqual(task.snapshot()['status'],'error')


if __name__=='__main__': unittest.main()
