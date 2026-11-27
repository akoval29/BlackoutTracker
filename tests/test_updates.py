import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from blackout_tracker.updates import (Release, extract_payload, parse_release, prepare_update, version_tuple)
from tools.portable_updater import install


class UpdateTests(unittest.TestCase):
    def release(self, tag='v0.14.0'):
        name = f'BlackoutTracker-{tag[1:]}-win-x64.zip'
        return {'tag_name': tag, 'assets': [{'name': name, 'state': 'uploaded', 'size': 123,
                'digest': 'sha256:' + 'a' * 64,
                'browser_download_url': f'https://github.com/akoval29/BlackoutTracker/releases/download/{tag}/{name}'}]}

    def test_numeric_versions_and_stable_only(self):
        self.assertGreater(version_tuple('v0.13.0'), version_tuple('0.9'))
        self.assertEqual(version_tuple('v0.12'), version_tuple('0.12.0'))
        self.assertIsNone(parse_release(self.release('v0.12'), '0.13.0'))
        self.assertIsNone(parse_release(dict(self.release(), prerelease=True)))
        self.assertEqual(parse_release(self.release()).version, '0.14.0')
        with self.assertRaises(ValueError):
            version_tuple('v1.0.0-beta')

    def test_reject_wrong_asset_digest_and_origin(self):
        for key, value in [('name', 'Source code.zip'), ('digest', None), ('browser_download_url', 'https://evil.example/file')]:
            release = self.release()
            release['assets'][0][key] = value
            with self.assertRaises(ValueError):
                parse_release(release)

    def archive(self, extra=None):
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w') as archive:
            for name in ['Blackout tracker.exe', 'Updater.exe', 'portable.flag', '_internal/python.dll']:
                archive.writestr('BlackoutTracker/' + name, b'payload')
            if extra:
                archive.writestr(extra, b'unsafe')
        return result.getvalue()

    def test_zip_traversal_and_user_data_rejected(self):
        for extra in ['BlackoutTracker/../escape', 'BlackoutTracker/data/settings.json', 'BlackoutTracker/_internal/../../escape', 'BlackoutTracker/_internal/C:evil']:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    extract_payload(io.BytesIO(self.archive(extra)), Path(directory))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_prepare_verifies_before_extract_and_preserves_data(self):
        data = self.archive()
        release = Release('0.14.0', 'https://example.test/update', hashlib.sha256(data).hexdigest(), len(data), '')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'Updater.exe').write_bytes(b'old trusted updater')
            (base / 'data').mkdir()
            settings = base / 'data/settings.json'
            settings.write_bytes(b'user settings')
            with patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
                workspace = prepare_update(release, base)
            self.assertEqual((workspace / 'Updater.exe').read_bytes(), b'old trusted updater')
            self.assertTrue((workspace / 'payload/BlackoutTracker/_internal/python.dll').exists())
            self.assertEqual(settings.read_bytes(), b'user settings')
            before = set(base.iterdir())
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'corrupt')):
                with self.assertRaises(ValueError):
                    prepare_update(release, base)
            self.assertEqual(set(base.iterdir()), before)

    def test_install_and_rollback_preserve_settings(self):
        for fail in [False, True]:
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                payload = base / 'payload'
                payload.mkdir()
                (base / 'data').mkdir()
                settings = base / 'data/settings.json'
                settings.write_text('keep')
                for folder, content in [(base, 'old'), (payload, 'new')]:
                    (folder / 'Blackout tracker.exe').write_text(content)
                    (folder / '_internal').mkdir()
                    (folder / '_internal/library').write_text(content)
                original = Path.rename
                def rename(source, destination):
                    if fail and source == payload / '_internal':
                        raise PermissionError('locked')
                    return original(source, destination)
                with patch.object(Path, 'rename', rename):
                    if fail:
                        with self.assertRaises(PermissionError):
                            install(payload, base, base / 'backup')
                    else:
                        install(payload, base, base / 'backup')
                self.assertEqual(settings.read_text(), 'keep')
                self.assertEqual((base / 'Blackout tracker.exe').read_text(), 'old' if fail else 'new')
                self.assertEqual((base / '_internal/library').read_text(), 'old' if fail else 'new')

    def test_check_does_not_download_until_click_and_opt_out(self):
        import sys
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        from blackout_tracker.ui.main_window import MainWindow
        from blackout_tracker.update_controller import UpdateController
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'portable.flag').touch()
            (base / 'Updater.exe').touch()
            with patch.object(MainWindow, 'refresh'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(base / 'Blackout tracker.exe')):
                window = MainWindow(base, '6.1')
                controller = UpdateController(window)
                window.updates = controller
                with patch('blackout_tracker.update_controller.check_release', return_value=parse_release(self.release())) as check, patch('blackout_tracker.update_controller.prepare_update', side_effect=ValueError('test download failed')) as download:
                    window.preferences['check_updates'] = False
                    controller.auto_check()
                    check.assert_not_called()
                    window.preferences['check_updates'] = True
                    controller.auto_check()
                    for _ in range(100):
                        QTest.qWait(10)
                        if controller.worker is None:
                            break
                    self.assertIsNone(controller.worker)
                    self.assertEqual(controller.release.version, '0.14.0')
                    download.assert_not_called()
                    controller.panel.update_button.click()
                    for _ in range(100):
                        QTest.qWait(10)
                        if controller.worker is None:
                            break
                    download.assert_called_once()
                    self.assertFalse(window.quitting)
                    self.assertTrue(controller.panel.update_button.isEnabled())
                controller.timer.stop()
                window.tick_timer.stop()
                window.poll_timer.stop()
                window.tray.hide()
                window.overlay.hide()
                window.deleteLater()
                app.processEvents()


if __name__ == '__main__':
    unittest.main()
