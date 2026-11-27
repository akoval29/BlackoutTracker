"""Exercise the built helper against a disposable application that writes started.txt.

Build the tiny fixture first (after build_portable.ps1):
python -m PyInstaller --noconfirm --onefile --windowed --distpath build/updater-smoke-dist
    --workpath build/updater-smoke-work --specpath build --name SmokeApp tools/updater_smoke_app.py
This never changes dist or a running BlackoutTracker instance.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


def wait_for(predicate, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError('Updater smoke check timed out')


def main():
    base = Path('build').resolve() / ('updater-smoke-' + uuid.uuid4().hex)
    workspace = base / '.blackout-update-test'
    payload = workspace / 'payload/BlackoutTracker'
    payload.mkdir(parents=True)
    (base / 'data').mkdir()
    (base / 'data/settings.json').write_text('{"group":"6.1"}')
    (base / 'Blackout tracker.exe').write_bytes(b'previous application')
    (base / '_internal').mkdir()
    (base / '_internal/old.dll').write_bytes(b'old')
    (payload / '_internal').mkdir()
    (payload / '_internal/new.dll').write_bytes(b'new')
    (payload / 'portable.flag').touch()
    helper = Path('build/updater-dist/Updater.exe').resolve()
    shutil.copy2(helper, workspace / 'Updater.exe')
    shutil.copy2(helper, payload / 'Updater.exe')
    shutil.copy2('build/updater-smoke-dist/SmokeApp.exe', payload / 'Blackout tracker.exe')
    sleeper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], creationflags=subprocess.CREATE_NO_WINDOW)
    updater = None
    try:
        updater = subprocess.Popen([str(workspace / 'Updater.exe'), str(workspace), str(sleeper.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
        wait_for(lambda: (workspace / 'ready').exists())
        assert (base / 'Blackout tracker.exe').read_bytes() == b'previous application'
        assert (base / '.update-in-progress').exists()
        sleeper.terminate()
        sleeper.wait(timeout=5)
        assert updater.wait(timeout=30) == 0
        wait_for(lambda: (base / 'started.txt').exists())
        assert (base / 'data/settings.json').read_text() == '{"group":"6.1"}'
        assert (workspace / 'backup/Blackout tracker.exe').read_bytes() == b'previous application'
        assert (base / '_internal/new.dll').exists()
        assert not (base / '_internal/old.dll').exists()
        assert not (base / '.update-in-progress').exists()
        print('Built updater: process wait, replacement, data preservation, backup and restart passed.')
    finally:
        for process in [sleeper, updater]:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()
