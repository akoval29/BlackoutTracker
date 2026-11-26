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
        raise OSError('Автозапуск доступний лише у Windows.')
    if enabled:
        command = startup_command()
        if len(command) > 260:
            raise OSError('Шлях надто довгий. Перемістіть програму в папку з коротшим шляхом.')
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


def migrate_renamed_executable():
    """Update only our existing legacy command in this portable directory.

    The registry value name stays unchanged, preserving Windows' separate
    startup approval state. Missing entries and registrations of other copies
    are never created or overwritten.
    """
    if winreg is None or not getattr(sys, 'frozen', False):
        return False
    executable = Path(sys.executable).resolve()
    if executable.name.casefold() == 'blackouttracker.exe':
        return False
    legacy_command = subprocess.list2cmdline([
        str(executable.with_name('BlackoutTracker.exe')), '--autostart'])
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            command, kind = winreg.QueryValueEx(key, VALUE_NAME)
            if kind != winreg.REG_SZ or command.casefold() != legacy_command.casefold():
                return False
            updated_command = startup_command()
            if len(updated_command) > 260:
                raise OSError('Шлях автозапуску надто довгий.')
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, updated_command)
            return True
    except FileNotFoundError:
        return False
