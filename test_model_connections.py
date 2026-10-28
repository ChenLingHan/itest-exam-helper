import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import MagicMock, patch
from desktop_bridge import Bridge
from model_connections import Connections, checked_ai, model_tool, tool_error


def ai(key='key-one',model='my-model'):
    return {'provider':'custom','base_url':'https://example.com/v1','model':model,'apikey':key}


class ConnectionTests(unittest.TestCase):
    def test_independent_keys_same_provider_survive_restart_and_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Connections(folder,{})
            one=store.save(None,'主账号',ai())
            two=store.save(None,'备用账号',ai('key-two','other-model'))
            store=Connections(folder,{})
            self.assertEqual(store.data['active_id'],two['id'])
            self.assertNotIn('key-one',json.dumps(store.summary()))
            self.assertNotIn('key-two',json.dumps(store.summary()))
            self.assertEqual(store.activate(one['id'])['ai']['apikey'],'key-one')
            store.save(one['id'],'修改名称',ai('new-key','new-model'))
            self.assertEqual(len(store.summary()['connections']),2)
            self.assertEqual(store.get(two['id'])['ai']['apikey'],'key-two')

    def test_migration_preserves_legacy_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Connections(folder,ai())
            self.assertEqual(store.get('migrated')['ai'],ai())
            self.assertEqual(Connections(folder,ai('changed')).get('migrated')['ai'],ai())

    def test_invalid_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder,'model_connections.yml');path.write_text('invalid: true')
            with self.assertRaises(ValueError): Connections(folder,ai())
            self.assertEqual(path.read_text(),'invalid: true')

    def test_credential_url_and_full_endpoint_rejected(self):
        for url in ('https://user:password@example.com/v1','https://example.com/v1?key=x','https://example.com/v1/chat/completions'):
            with self.subTest(url=url),self.assertRaises(ValueError): checked_ai({**ai(),'base_url':url})
        checked_ai(ai(model=''),need_model=False)

    def test_bridge_inactive_keys_are_redacted_and_switching_is_guarded(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder)
            one=bridge.change_connection('save',{'id':None,'name':'主','ai':ai('private-one')})
            two=bridge.change_connection('save',{'id':None,'name':'备','ai':ai('private-two')})
            self.assertTrue(one['ok'] and two['ok'])
            self.assertEqual(bridge._redact('private-one private-two'),'*** ***')
            self.assertNotIn('private-one',json.dumps(bridge.get_state()))
            bridge._state['busy']=True
            self.assertFalse(bridge.change_connection('activate',{'id':one['selected']['id']})['ok'])
            bridge._state['busy']=False
            bridge.change_connection('activate',{'id':one['selected']['id']})
            self.assertEqual(Bridge(folder).get_config()['ai']['apikey'],'private-one')

    def test_tools_are_explicit_async_and_errors_do_not_echo_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge=Bridge(folder);gate=threading.Event()
            def work(value,kind):
                gate.wait(2)
                raise RuntimeError('request included private-one')
            with patch('desktop_bridge.model_tool',side_effect=work) as call:
                bridge.get_connections();bridge.get_config();call.assert_not_called()
                result=bridge.start_model_tool('models',ai('private-one'))
                self.assertTrue(result['ok'])
                self.assertTrue(bridge.get_state()['model_tools']['busy'])
                self.assertFalse(bridge.start_model_tool('test',ai())['ok'])
                gate.set()
                deadline=time.monotonic()+2
                while bridge.get_state()['model_tools']['busy'] and time.monotonic()<deadline: time.sleep(.01)
                state=bridge.get_state()['model_tools']
                self.assertFalse(state['busy'])
                self.assertFalse(state['ok'])
                self.assertNotIn('private-one',json.dumps(state))

    def test_model_tools_construct_requests_without_external_calls(self):
        client=MagicMock()
        client.models.list.return_value.data=[types.SimpleNamespace(id='b'),types.SimpleNamespace(id='a'),types.SimpleNamespace(id='a')]
        client.chat.completions.create.return_value.choices=[types.SimpleNamespace(finish_reason='stop',message=types.SimpleNamespace(content='{"ok":true}'))]
        with patch('openai.OpenAI',return_value=client):
            self.assertEqual(model_tool(ai(),'models')['models'],['a','b'])
            client.chat.completions.create.assert_not_called()
            client.models.list.return_value.data=[]
            empty=model_tool(ai(),'models')
            self.assertFalse(empty['ok']);self.assertEqual(empty['models'],[])
            self.assertTrue(model_tool(ai(),'test')['ok'])
            self.assertEqual(client.chat.completions.create.call_args.kwargs['response_format'],{'type':'json_object'})
        self.assertEqual(tool_error(types.SimpleNamespace(status_code=401)),'鉴权失败：请检查 API Key、所属地域及模型权限。')


if __name__=='__main__': unittest.main()
