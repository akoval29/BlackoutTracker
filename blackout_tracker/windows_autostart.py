"""Per-user Windows startup registration; no installation or elevation."""
import subprocess
import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'BlackoutTracker'


def startup_command():
    executable = Path(sys.executable).resolve()
    if getattr(sys, 'frozen', False):
        arguments = [str(executable)]
    else:
        pythonw = executable.with_name('pythonw.exe')
        arguments = [str(pythonw if pythonw.exists() else executable),
                     str(Path(__file__).resolve().parent.parent / 'main.py')]
    return subprocess.list2cmdline(arguments + ['--autostart'])


def is_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, kind = winreg.QueryValueEx(key, VALUE_NAME)
        return kind == winreg.REG_SZ and command == startup_command()
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    if winreg is None:
        raise OSError('РђРІС‚РѕР·Р°РїСѓСЃРє РґРѕСЃС‚СѓРїРЅРёР№ Р»РёС€Рµ Сѓ Windows.')
    if enabled:
        command = startup_command()
        if len(command) > 260:
            raise OSError('РЁР»СЏС… РЅР°РґС‚Рѕ РґРѕРІРіРёР№. РџРµСЂРµРјС–СЃС‚С–С‚СЊ РїСЂРѕРіСЂР°РјСѓ РІ РїР°РїРєСѓ Р· РєРѕСЂРѕС‚С€РёРј С€Р»СЏС…РѕРј.')
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
