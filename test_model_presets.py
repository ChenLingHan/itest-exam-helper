"""No external calls: preset migration, isolation, and request compatibility."""
import tempfile
import unittest
from pathlib import Path
import yaml
from desktop_bridge import Bridge
from model_presets import get_presets, normalize_ai, infer_provider, request_options


class ModelPresetTests(unittest.TestCase):
    def test_catalog_has_only_the_four_requested_providers(self):
        self.assertEqual({p['id'] for p in get_presets()},{'deepseek','openai','zhipu','kimi'})

    def test_key_only_presets_have_canonical_endpoint_and_model(self):
        for preset in get_presets():
            with self.subTest(provider=preset['id']):
                ai=normalize_ai({'provider':preset['id'], 'apikey':'test-only'})
                self.assertEqual(ai['base_url'],preset['base_url'])
                self.assertEqual(ai['model'],preset['model'])
                self.assertEqual(ai['apikey'],'test-only')
                self.assertEqual(infer_provider(ai),preset['id'])

    def test_custom_and_legacy_configuration_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            ai={'base_url':'https://example.com/v1','model':'my-model','apikey':'private-test-key'}
            Path(folder,'config.yml').write_text(yaml.safe_dump({'username':'test','password':'test','ai':ai}),encoding='utf-8')
            bridge=Bridge(folder)
            self.assertEqual(bridge.get_config()['ai'],{**ai,'provider':'custom'})
            config=bridge._normalize({'ai':ai})
            self.assertEqual(config['ai'],{**ai,'provider':'custom'})

    def test_preset_seeds_defaults_and_retains_explicit_user_edits(self):
        ai=normalize_ai({'provider':'deepseek','base_url':'https://example.com','model':'wrong','apikey':'test'})
        self.assertEqual(ai['base_url'],'https://example.com')
        self.assertEqual(ai['model'],'wrong')
        with self.assertRaises(ValueError):
            normalize_ai({'provider':'unknown'})

    def test_provider_specific_parameters_do_not_leak_to_custom_endpoint(self):
        ai=normalize_ai({'provider':'qwen-cn','apikey':'test'})
        self.assertEqual(request_options(ai),{'extra_body':{'enable_thinking':False}})
        ai['base_url']='https://example.com/v1'
        self.assertEqual(request_options(ai),{})
        self.assertEqual(request_options(normalize_ai({'provider':'openai'})),{})

    def test_preset_metadata_has_no_keys_and_is_copied(self):
        presets=get_presets()
        self.assertTrue(all('apikey' not in p for p in presets))
        presets[0]['extra_body']['thinking']['type']='changed'
        self.assertEqual(get_presets()[0]['extra_body']['thinking']['type'],'disabled')


if __name__=='__main__':
    unittest.main()
