from blackout_tracker.windows_autostart import migrate_renamed_executable
"""Application startup, single-instance lock and event loop."""
from blackout_tracker.resources import ASSETS_DIRECTORY
import json
import sys
from pathlib import Path
from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMessageBox
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, groups_for
from blackout_tracker.schedule import KYIV_TIMEZONE
from blackout_tracker.resources import load_app_icon
from blackout_tracker.storage import save_json_atomic
from blackout_tracker.storage import get_data_directory
from blackout_tracker.single_instance import ActivationServer, request_activation
from blackout_tracker.ui.setup_dialog import SetupDialog
from blackout_tracker.ui.main_window import MainWindow
from blackout_tracker.ui.theme import APP_STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('BlackoutTracker')
    from blackout_tracker.version import VERSION
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(load_app_icon())
    app.setStyle('Fusion')
    app.setStyleSheet(APP_STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    if len(sys.argv) == 3 and sys.argv[1] == '--audio-self-test':
        from blackout_tracker.audio_diagnostics import run_audio_check
        return run_audio_check(app, sys.argv[2])
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        # Packaging smoke check: exercise bundled Qt, zoneinfo and widgets, then exit.
        from PySide6.QtGui import QFontDatabase
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        report = Path(sys.argv[2]).resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        MainWindow.refresh = lambda self: None
        window = MainWindow(report.parent, '6.1')
        setup = window.settings_panel
        app.processEvents()
        window.grab().save(str(report.with_suffix('.png')))
        save_json_atomic(report, {'ok': True, 'frozen': bool(getattr(sys, 'frozen', False)),
                           'timezone': str(KYIV_TIMEZONE), 'queue': setup.queue_selector.currentText(),
                           'qt_widgets': True, 'sound_assets': all((ASSETS_DIRECTORY / 'audio' / language / name).exists() for language in ('ua', 'en', 'de') for name in ('common_attention.mp3', 'power_outage_in_5_minutes.mp3', 'power_outage_in_10_minutes.mp3')), 'tray_available': QSystemTrayIcon.isSystemTrayAvailable()})
        window.tray.hide()
        return 0
    folder = get_data_directory()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        QMessageBox.critical(None, 'BlackoutTracker', f'Не вдається створити папку даних. Для portable оберіть папку з правом запису.\n{exc}')
        return 1
    lock = QLockFile(str(folder / 'app.lock'))
    if not lock.tryLock(100):
        if '--autostart' not in sys.argv:
            request_activation(folder)
        return 0
    activation_server = ActivationServer(folder, app)
    try:
        stored = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))
        group = stored['group']
        if stored.get('region', DEFAULT_REGION) not in REGIONS or group not in groups_for(stored.get('region', DEFAULT_REGION)):
            raise ValueError('Invalid group')
    except (OSError, ValueError, KeyError, TypeError):
        dialog = SetupDialog('6.1')
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        group = dialog.queue_selector.currentText()
        save_json_atomic(folder / 'settings.json', {'region': dialog.region_selector.currentData(), 'group': group})
    autostart_error = ''
    try:
        migrate_renamed_executable()
    except OSError as exc:
        autostart_error = f'Не вдалося оновити шлях автозапуску: {exc}'
    window = MainWindow(folder, group)
    activation_server.set_handler(window.reveal_compact)
    from blackout_tracker.update_controller import UpdateController
    window.updates = UpdateController(window)
    if autostart_error:
        window.settings_panel.autostart_error.setText(autostart_error)
        window.settings_panel.autostart_error.show()
    if '--autostart' not in sys.argv or not QSystemTrayIcon.isSystemTrayAvailable():
        window.show()
    return app.exec()

