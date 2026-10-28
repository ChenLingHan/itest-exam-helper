"""Packaging boundaries and worker protocol regression checks, without website access."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import app_paths


class ReleaseTests(unittest.TestCase):
    def test_worker_protocol_roundtrips_unicode(self):
        probe='中文/日本語/é'
        result=subprocess.run(app_paths.worker_command()+['--protocol-test'],input=json.dumps({'probe':probe},ensure_ascii=False)+'\n',
                              text=True,encoding='utf-8',capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)['echo'],probe)
        self.assertTrue(result.stdout.isascii())

    def test_frozen_worker_does_not_require_python(self):
        with patch.object(app_paths, 'FROZEN', True), patch.object(sys, 'executable', r'C:\Apps\iTEST.exe'):
            command = app_paths.worker_command()
            self.assertEqual(Path(command[0]).name, 'iTEST-worker.exe')
            self.assertEqual(len(command), 1)

    def test_worker_closes_without_credentials_or_browser(self):
        result = subprocess.run(app_paths.worker_command(), input='{"action":"close"}\n',
                                text=True, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_example_has_no_credentials(self):
        import yaml
        config = yaml.safe_load((app_paths.RESOURCE_ROOT/'config.example.yml').read_text(encoding='utf-8'))
        self.assertEqual(config['username'], '')
        self.assertEqual(config['password'], '')
        self.assertEqual(config['ai']['apikey'], '')


if __name__ == '__main__':
    unittest.main()
