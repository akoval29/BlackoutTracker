"""Standalone helper, bundled as one-file Updater.exe; does not depend on Qt."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

NAMES = ('Blackout tracker.exe', '_internal', 'Updater.exe', 'portable.flag', 'README.txt', 'licenses')


def install(payload, base, backup):
    """Replace only owned files; restore the previous payload on a handled failure."""
    backup.mkdir()
    moved, placed = [], []
    try:
        for name in NAMES:
            target = base / name
            if target.exists():
                target.rename(backup / name)
                moved.append(name)
            source = payload / name
            if source.exists():
                source.rename(target)
                placed.append(name)
    except Exception:
        for name in reversed(placed):
            target = base / name
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        for name in reversed(moved):
            (backup / name).rename(base / name)
        raise


def main():
    workspace = Path(sys.argv[1]).resolve()
    base = workspace.parent
    marker = base / '.update-in-progress'
    handle = None
    owns_marker = False
    try:
        if not workspace.name.startswith('.blackout-update-') or workspace == base:
            raise ValueError('Invalid update workspace')
        payload = workspace / 'payload' / 'BlackoutTracker'
        if not all((payload / name).exists() for name in NAMES[:4]):
            raise ValueError('Incomplete update payload')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, int(sys.argv[2]))
        if not handle:
            raise OSError('Cannot observe application process')
        with marker.open('x', encoding='utf-8') as output:
            json.dump({'workspace': str(workspace), 'pid': os.getpid()}, output)
        owns_marker = True
        (workspace / 'ready').touch()
        if kernel.WaitForSingleObject(handle, 120000) != 0:
            raise TimeoutError('Програма не завершила роботу за 2 хвилини. Оновлення скасовано.')
        install(payload, base, workspace / 'backup')
        marker.unlink()
        owns_marker = False
        subprocess.Popen([str(base / 'Blackout tracker.exe')], cwd=base)
        (workspace / 'success').touch()
    except Exception as exc:
        (workspace / 'error.txt').write_text(str(exc), encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None, f'Не вдалося завершити оновлення.\n{exc}\n\nРезервна копія (якщо створена):\n{workspace / "backup"}', 'BlackoutTracker', 0x10)
        return 1
    finally:
        if handle:
            kernel.CloseHandle(handle)
        if owns_marker:
            marker.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
