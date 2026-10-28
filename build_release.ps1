param([string]$ISCC = 'ISCC.exe')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# Only resources explicitly declared in iTEST.spec enter the distribution.
if (!(Test-Path 'model/am/final.mdl') -or !(Test-Path 'lib/ffmpeg.exe')) {
    throw 'Obtain the Vosk English model and FFmpeg described in README.md first.'
}
python -m PyInstaller --noconfirm --clean iTEST.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$licenses = 'dist/iTEST/_internal/third-party-licenses'
New-Item -ItemType Directory -Force $licenses | Out-Null
python -c "import importlib.metadata as m,pathlib,shutil; root=pathlib.Path('$licenses'); [( (root/d.metadata['Name']/str(f)).parent.mkdir(parents=True,exist_ok=True),shutil.copyfile(d.locate_file(f),root/d.metadata['Name']/str(f))) for d in m.distributions() for f in (d.files or []) if ('license' in str(f).lower() or 'copying' in str(f).lower()) and d.locate_file(f).is_file()]"
& 'dist/iTEST/iTEST-worker.exe' --self-test
if ($LASTEXITCODE -ne 0) { throw 'Frozen runtime self-test failed' }
python verify_frozen_protocol.py
if ($LASTEXITCODE -ne 0) { throw 'Frozen Unicode protocol test failed' }
& 'dist/iTEST/iTEST-worker.exe' --browser-test
if ($LASTEXITCODE -ne 0) { throw 'Frozen Edge browser test failed' }
& $ISCC installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
$releaseVersion = python -c "from app_paths import VERSION; print(VERSION)"
$sums = Get-Item "release/iTEST-Exam-Helper-$releaseVersion-windows-x64-setup.exe" | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($_.Name)"
}

$sums | Set-Content -Encoding ascii release/SHA256SUMS.txt
