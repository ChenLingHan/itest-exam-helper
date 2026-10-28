"""Create an explicit allowlist staging tree and check it against local secrets."""
from pathlib import Path
import shutil
import yaml

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'publish'
FILES = ['app_paths.py', 'desktop_bridge.py', 'exam_runner.py', 'gui.py', 'gui_worker.py',
         'model_presets.py', 'test_model_presets.py', 'MODEL_PRESETS.md', 'exam_schema.py', 'test_exam_schema.py', 'task_progress.py', 'itest.py', 'kimi_model.py', 'main.py', 'mp32str.py',
         'test_gui.py', 'test_task_progress.py', 'test_desktop_ui.py', 'test_close_ui.py',
         'requirements.txt', 'requirements-gui.txt', 'requirements-lock.txt',
         'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'config.example.yml',
         '.gitignore', 'iTEST.spec', 'installer.iss', 'build_release.ps1',
         'prepare_release.py', 'RELEASE_NOTES.md', 'test_release.py']


def main():
    DEST.mkdir(exist_ok=True)
    for name in FILES:
        shutil.copy2(ROOT/name, DEST/name)
    for directory in ('ui', 'assets', '.github'):
        shutil.copytree(ROOT/directory, DEST/directory, dirs_exist_ok=True)
    # Read secrets for comparison only; never print their values or copy config.yml.
    config = yaml.safe_load((ROOT/'config.yml').read_text(encoding='utf-8')) or {}
    secrets = [str(config.get(k) or '') for k in ('username', 'password')]
    secrets += [str(config.get('ai', {}).get('apikey') or '')]
    forbidden = ('config.yml', '.env', '.lnk', '.bak', '.log', '.pyc', '.pfx', '.pem')
    count = 0
    candidates = [DEST/name for name in FILES]
    for directory in ('ui', 'assets', '.github'):
        candidates.extend(p for p in (DEST/directory).rglob('*') if p.is_file())
    for path in candidates:
        if path.name == 'config.yml' or path.suffix in forbidden[1:]:
            raise RuntimeError('Forbidden file in publish directory: '+str(path.relative_to(DEST)))
        data = path.read_bytes()
        if any(secret.encode() in data for secret in secrets if len(secret) >= 4):
            raise RuntimeError('Local credential found in: '+str(path.relative_to(DEST)))
        count += 1
    print(f'Allowlist staging passed: {count} files; no local credential matches.')


if __name__ == '__main__':
    main()
