"""UI orchestration: background discovery, explicit consent, then helper handoff."""
import os
from pathlib import Path
import subprocess
import sys
import time

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from blackout_tracker.updates import check_release, prepare_update
from blackout_tracker.version import VERSION


class UpdateWorker(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, release=None):
        super().__init__()
        self.release = release

    def run(self):
        try:
            self.result.emit(check_release() if self.release is None else prepare_update(
                self.release, Path(sys.executable).parent, self.progress.emit, self.isInterruptionRequested))
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.panel = window.settings_panel
        self.worker = None
        self.release = None
        self.installing = False
        self.helper = None
        self.panel.update_button.clicked.connect(self.clicked)
        self.panel.auto_updates.toggled.connect(self.preference_changed)
        self.action = self.make_action()
        window.tray.contextMenu().insertAction(window.tray.contextMenu().actions()[-1], self.action)
        self.timer = QTimer(self)
        self.timer.setInterval(6 * 60 * 60 * 1000)
        self.timer.timeout.connect(self.auto_check)
        self.timer.start()
        self.handoff_timer = QTimer(self)
        self.handoff_timer.setInterval(100)
        self.handoff_timer.timeout.connect(self.poll_helper)
        self.supported = (sys.platform == 'win32' and getattr(sys, 'frozen', False)
                          and (Path(sys.executable).parent / 'portable.flag').is_file()
                          and (Path(sys.executable).parent / 'Updater.exe').is_file())
        if self.supported:
            QTimer.singleShot(10000, self.auto_check)
        else:
            self.panel.update_status.setText(f'Версія {VERSION}. Оновлення доступні у portable-збірці.')
            self.panel.update_button.setEnabled(False)
            self.action.setEnabled(False)

    def make_action(self):
        from PySide6.QtGui import QAction
        action = QAction('Перевірити оновлення програми', self)
        action.triggered.connect(self.clicked)
        return action

    def preference_changed(self, enabled):
        if enabled:
            self.auto_check()

    def auto_check(self):
        if self.window.preferences.get('check_updates', True) and self.supported:
            self.start_worker()

    def clicked(self):
        if not self.supported or self.worker or self.installing:
            return
        self.start_worker(self.release)

    def start_worker(self, release=None):
        if self.worker or self.installing or self.window.quitting:
            return
        self.panel.update_button.setEnabled(False)
        self.action.setEnabled(False)
        self.panel.update_status.setText('Завантаження оновлення…' if release else 'Перевіряємо GitHub Releases…')
        self.worker = UpdateWorker(release)
        self.worker.result.connect(self.prepared if release else self.checked)
        self.worker.failed.connect(self.failed)
        self.worker.progress.connect(lambda percent: self.panel.update_status.setText(f'Завантаження: {percent}%'))
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def checked(self, release):
        self.release = release
        if release:
            self.panel.update_status.setText(f'Доступна версія {release.version}. Налаштування збережуться.')
            self.panel.update_notes.setText(release.notes)
            self.panel.update_notes.setVisible(bool(release.notes))
            self.panel.update_button.setText('Оновити й перезапустити')
            self.action.setText(f'Оновити до {release.version} й перезапустити')
            self.window.settings.setText('Налаштування • Оновлення')
        else:
            self.panel.update_status.setText(f'Версія {VERSION} актуальна.')
            self.panel.update_button.setText('Перевірити оновлення')
            self.action.setText('Перевірити оновлення програми')
            self.window.settings.setText('Налаштування')
            self.panel.update_notes.hide()

    def failed(self, message):
        self.panel.update_status.setText(f'Оновлення не виконано: {message}')

    def finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.panel.update_button.setEnabled(not self.installing)
        self.action.setEnabled(not self.installing)
        if self.window.quitting:
            self.window.quit_app()

    def prepared(self, workspace):
        if self.window.quitting:
            return
        self.workspace = workspace
        try:
            self.helper = subprocess.Popen([str(workspace / 'Updater.exe'), str(workspace), str(os.getpid())],
                                           cwd=workspace, creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self.failed(str(exc))
            return
        self.installing = True
        self.deadline = time.monotonic() + 30
        self.panel.update_status.setText('Готуємо перезапуск…')
        self.handoff_timer.start()

    def poll_helper(self):
        if (self.workspace / 'ready').exists() and self.helper.poll() is None:
            self.handoff_timer.stop()
            self.window.quit_app()
        elif self.helper.poll() is not None or time.monotonic() > self.deadline:
            self.handoff_timer.stop()
            if self.helper.poll() is None:
                self.helper.terminate()
                self.helper.wait(timeout=5)
                # No files have been replaced: the main process is still alive.
                (self.workspace.parent / '.update-in-progress').unlink(missing_ok=True)
            self.installing = False
            self.failed('Не вдалося запустити updater. Програма продовжує працювати.')
            self.panel.update_button.setEnabled(True)
            self.action.setEnabled(True)
