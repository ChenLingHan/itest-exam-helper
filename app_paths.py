"""Separate bundled read-only resources from per-user runtime data."""
import os
from pathlib import Path
import sys

FROZEN = getattr(sys, 'frozen', False)
RESOURCE_ROOT = Path(__file__).resolve().parent
DATA_ROOT = (Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'iTEST-Exam-Helper') if FROZEN else RESOURCE_ROOT
VERSION = '1.1.0-beta.8'


def worker_command():
    if FROZEN:
        return [str(Path(sys.executable).with_name('iTEST-worker.exe'))]
    python = str(Path(sys.executable).with_name('python.exe')) if os.name == 'nt' else sys.executable
    return [python, '-u', str(RESOURCE_ROOT / 'gui_worker.py')]
