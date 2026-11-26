import unittest
from unittest.mock import MagicMock, patch
import blackout_tracker.windows_autostart as autostart


class AutostartTests(unittest.TestCase):
    def test_frozen_command_quotes_path_and_starts_in_tray(self):
        with patch.object(autostart.sys, 'frozen', True, create=True), patch.object(autostart.sys, 'executable', r'C:\Моя програма\Blackout tracker.exe'):
            self.assertEqual(autostart.startup_command(), '"C:\\Моя програма\\Blackout tracker.exe" --autostart')

    def test_registration_is_per_user_and_removal_only_deletes_own_value(self):
        registry = MagicMock()
        with patch.object(autostart, 'winreg', registry), patch.object(autostart, 'startup_command', return_value='BlackoutTracker.exe --autostart'):
            autostart.set_enabled(True)
            registry.CreateKeyEx.assert_called_once_with(registry.HKEY_CURRENT_USER, autostart.RUN_KEY, 0, registry.KEY_SET_VALUE)
            registry.SetValueEx.assert_called_once_with(registry.CreateKeyEx.return_value.__enter__.return_value, 'BlackoutTracker', 0, registry.REG_SZ, 'BlackoutTracker.exe --autostart')
            autostart.set_enabled(False)
            registry.DeleteValue.assert_called_once_with(registry.OpenKey.return_value.__enter__.return_value, 'BlackoutTracker')

    def test_other_copy_is_not_enabled(self):
        registry = MagicMock()
        registry.QueryValueEx.return_value = ('old.exe --autostart', registry.REG_SZ)
        with patch.object(autostart, 'winreg', registry), patch.object(autostart, 'startup_command', return_value='new.exe --autostart'):
            self.assertFalse(autostart.is_enabled())
            registry.QueryValueEx.return_value = ('new.exe --autostart', registry.REG_SZ)
            self.assertTrue(autostart.is_enabled())

    def test_missing_registration_and_permission_error(self):
        registry = MagicMock()
        registry.OpenKey.side_effect = FileNotFoundError
        with patch.object(autostart, 'winreg', registry):
            self.assertFalse(autostart.is_enabled())
            autostart.set_enabled(False)
            registry.CreateKeyEx.side_effect = PermissionError
            with self.assertRaises(PermissionError):
                autostart.set_enabled(True)

    def test_long_command_is_rejected_before_writing(self):
        registry = MagicMock()
        with patch.object(autostart, 'winreg', registry), patch.object(autostart, 'startup_command', return_value='x' * 261):
            with self.assertRaises(OSError):
                autostart.set_enabled(True)
            registry.CreateKeyEx.assert_not_called()

    def test_source_command_uses_existing_entry_point(self):
        from pathlib import Path
        with patch.object(autostart.sys, 'frozen', False, create=True):
            command = autostart.startup_command()
            entry_point = Path(autostart.__file__).resolve().parent.parent / 'main.py'
            self.assertTrue(entry_point.is_file())
            self.assertIn(str(entry_point), command)
            self.assertTrue(command.endswith('--autostart'))

    def test_rename_migrates_only_existing_same_directory_registration(self):
        registry = MagicMock()
        registry.REG_SZ = 1
        registry.KEY_QUERY_VALUE = 1
        registry.KEY_SET_VALUE = 2
        old = '"C:\\Моя програма\\BlackoutTracker.exe" --autostart'
        new = '"C:\\Моя програма\\Blackout tracker.exe" --autostart'
        with patch.object(autostart, 'winreg', registry), patch.object(autostart.sys, 'frozen', True, create=True), patch.object(autostart.sys, 'executable', r'C:\Моя програма\Blackout tracker.exe'):
            registry.QueryValueEx.return_value = (old, registry.REG_SZ)
            self.assertTrue(autostart.migrate_renamed_executable())
            registry.SetValueEx.assert_called_once_with(registry.OpenKey.return_value.__enter__.return_value, autostart.VALUE_NAME, 0, registry.REG_SZ, new)
            for command in (new, r'C:\Other\BlackoutTracker.exe --autostart', old + ' --extra'):
                registry.SetValueEx.reset_mock()
                registry.QueryValueEx.return_value = (command, registry.REG_SZ)
                self.assertFalse(autostart.migrate_renamed_executable())
                registry.SetValueEx.assert_not_called()
            registry.QueryValueEx.side_effect = FileNotFoundError
            self.assertFalse(autostart.migrate_renamed_executable())
            registry.SetValueEx.assert_not_called()
            registry.CreateKeyEx.assert_not_called()

    def test_source_run_never_migrates_registry(self):
        registry = MagicMock()
        with patch.object(autostart, 'winreg', registry), patch.object(autostart.sys, 'frozen', False, create=True):
            self.assertFalse(autostart.migrate_renamed_executable())
            registry.OpenKey.assert_not_called()
