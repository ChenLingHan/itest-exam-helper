"""Verify Unicode pipe I/O in the real bundled executable, without browser/login."""
import json
from pathlib import Path
import subprocess


def main():
    worker=Path('dist/iTEST/iTEST-worker.exe').resolve()
    probe='\u4e2d\u6587/\u65e5\u672c\u8a9e/\u00e9'
    result=subprocess.run([str(worker),'--protocol-test'],input=json.dumps({'probe':probe},ensure_ascii=False)+'\n',
                          text=True,encoding='utf-8',capture_output=True,timeout=20)
    assert result.returncode==0,'Frozen protocol probe failed'
    output=json.loads(result.stdout)
    assert output['echo']==probe and output['message']=='\u4e2d\u6587\u901a\u4fe1\u6b63\u5e38'
    assert result.stdout.isascii(),'Protocol output must be code-page independent'
    print('Frozen Unicode protocol OK')


if __name__=='__main__': main()
