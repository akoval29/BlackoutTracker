import unittest
from unittest.mock import MagicMock, patch
import autostart


class AutostartTests(unittest.TestCase):
    def test_frozen_command_quotes_path_and_starts_in_tray(self):
        with patch.object(autostart.sys, 'frozen', True, create=True), patch.object(autostart.sys, 'executable', r'C:\Моя програма\BlackoutTracker.exe'):
            self.assertEqual(autostart.startup_command(), '"C:\\Моя програма\\BlackoutTracker.exe" --autostart')

    def test_registration_is_per_user_and_removal_only_deletes_own_value(self):
        registry = MagicMock()
        with patch.object(autostart, 'winreg', registry), patch.object(autostart, 'startup_command', return_value='app.exe --autostart'):
            autostart.set_enabled(True)
            registry.CreateKeyEx.assert_called_once_with(registry.HKEY_CURRENT_USER, autostart.RUN_KEY, 0, registry.KEY_SET_VALUE)
            registry.SetValueEx.assert_called_once_with(registry.CreateKeyEx.return_value.__enter__.return_value, 'BlackoutTracker', 0, registry.REG_SZ, 'app.exe --autostart')
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
