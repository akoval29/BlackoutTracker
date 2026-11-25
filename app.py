import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QLockFile
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QDialogButtonBox, QSystemTrayIcon, QMenu,
    QFrame, QMessageBox, QScrollArea)
from core import GROUPS, KYIV, fetch_schedule, state_at, fresh, timestamp, clock_text

STYLE = '''
QWidget { background: #101722; color: #e9eff9; font-family: "Segoe UI"; font-size: 14px; }
QLabel { background: transparent; }
QFrame#card { background: #1a2535; border: 1px solid #2a394e; border-radius: 14px; }
QPushButton, QComboBox { background: #24344a; padding: 9px 15px; border: 1px solid #3b4e67; border-radius: 7px; }
QPushButton:hover { background: #324760; }
QPushButton:disabled { color: #8190a8; }
QLabel#muted { color: #a6b6cd; }
QMenu { background: #1a2535; padding: 6px; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background: #324760; }
'''


def icon(color):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor('#101722'))
    painter.setFont(QFont('Segoe UI', 32, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'ϟ')
    painter.end()
    return QIcon(pixmap)


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def data_directory():
    override = os.environ.get('BLACKOUT_DATA_DIR')
    if override:
        return Path(override)
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    if (base / 'portable.flag').exists():
        return base / 'data'
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'BlackoutTracker'


class Setup(QDialog):
    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Налаштування BlackoutTracker')
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel('Оберіть свою чергу')
        title.setStyleSheet('font-size: 24px; font-weight: 600;')
        layout.addWidget(title)
        layout.addWidget(QLabel('Київська область · ДТЕК КРЕМ'))
        note = QLabel('Перша версія підтримує Київську область.\nЧергу можна змінити будь-коли в налаштуваннях.')
        note.setObjectName('muted')
        layout.addWidget(note)
        source_note = QLabel('Дані з відкритого джерела GPV-UA: https://gpv-ua.com/\nГрафік може змінюватися й не підтверджує фактичну наявність світла.')
        source_note.setWordWrap(True)
        source_note.setObjectName('muted')
        layout.addWidget(source_note)
        self.combo = QComboBox()
        self.combo.addItems(GROUPS)
        self.combo.setCurrentText(group)
        self.combo.setAccessibleName('Черга відключень')
        layout.addWidget(self.combo)
        buttons = QDialogButtonBox()
        buttons.addButton('Зберегти', QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton('Скасувати', QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class Fetcher(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, group):
        super().__init__()
        self.group = group

    def run(self):
        try:
            self.ready.emit(fetch_schedule(self.group))
        except Exception as exc:
            self.failed.emit(str(exc))


class Window(QMainWindow):
    def __init__(self, folder, group):
        super().__init__()
        self.folder, self.group = folder, group
        self.schedule = None
        self.worker = None
        self.offline = False
        self.quitting = False
        self.last_color = None
        self.setWindowTitle('BlackoutTracker')
        self.expanded = False
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel('BlackoutTracker')
        title.setStyleSheet('font-size: 22px; font-weight: 700;')
        header.addWidget(title)
        header.addStretch()
        hide = QPushButton('×')
        hide.setAccessibleName('Сховати у трей')
        hide.setToolTip('Сховати у трей')
        hide.setFixedWidth(40)
        hide.clicked.connect(self.hide_to_tray)
        header.addWidget(hide)
        layout.addLayout(header)
        self.subtitle = QLabel()
        self.subtitle.setObjectName('muted')
        layout.addWidget(self.subtitle)
        card = QFrame()
        card.setObjectName('card')
        cardlayout = QVBoxLayout(card)
        cardlayout.setContentsMargins(16, 16, 16, 16)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.countdown = QLabel('—')
        self.countdown.setStyleSheet('font-size: 48px; font-weight: 650;')
        self.target = QLabel()
        self.target.setObjectName('muted')
        for label in (self.status, self.countdown, self.target):
            cardlayout.addWidget(label)
        layout.addWidget(card)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet('color: #f6ad55; font-size: 12px;')
        layout.addWidget(self.warning)
        self.details = QScrollArea()
        self.details.setWidgetResizable(True)
        self.details.setFrameShape(QFrame.Shape.NoFrame)
        details_body = QWidget()
        details_layout = QVBoxLayout(details_body)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(12)
        self.details.setWidget(details_body)
        self.day_labels = []
        for _ in range(2):
            label = QLabel()
            label.setWordWrap(True)
            label.setMinimumHeight(68)
            label.setTextFormat(Qt.TextFormat.PlainText)
            details_layout.addWidget(label)
            self.day_labels.append(label)
        self.source = QLabel()
        self.source.setWordWrap(True)
        self.source.setObjectName('muted')
        details_layout.addWidget(self.source)
        attribution = QLabel('Відкриті дані: <a href="https://gpv-ua.com/" style="color:#5ee0af">GPV-UA</a> · резерв: GitHub')
        attribution.setOpenExternalLinks(True)
        details_layout.addWidget(attribution)
        row = QHBoxLayout()
        self.refresh_button = QPushButton('Оновити графік')
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        self.settings = QPushButton('Обрати чергу')
        self.settings.clicked.connect(self.configure)
        row.addWidget(self.settings)
        details_layout.addLayout(row)
        footer = QLabel('Час за Києвом · Дані описують план, а не фактичний стан мережі.')
        footer.setWordWrap(True)
        footer.setObjectName('muted')
        details_layout.addWidget(footer)
        details_layout.addStretch()
        layout.addWidget(self.details, 1)
        self.details.hide()
        self.expand_button = QPushButton('Розгорнути · графік і подробиці ↑')
        self.expand_button.clicked.connect(self.toggle_expanded)
        layout.addWidget(self.expand_button)
        self.tray = QSystemTrayIcon(icon('#8190a8'), self)
        menu = QMenu(self)
        menu.addAction('Відкрити графік', self.reveal)
        menu.addAction('Оновити', self.refresh)
        menu.addAction('Обрати чергу', self.configure)
        menu.addSeparator()
        menu.addAction('Вийти', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.activated)
        self.tray.show()
        self.load_cache()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh)
        self.poll_timer.start(120_000)
        self.tick()
        self.dock_screen = QApplication.primaryScreen()
        self.dock_screen.availableGeometryChanged.connect(self.anchor)
        QApplication.instance().primaryScreenChanged.connect(self.screen_changed)
        self.anchor()
        QTimer.singleShot(0, self.refresh)

    def screen_changed(self, screen):
        self.dock_screen = screen
        if screen:
            screen.availableGeometryChanged.connect(self.anchor)
            self.anchor()

    def anchor(self, *_):
        screen = self.dock_screen or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        width = min(420, area.width() - 24)
        height = min(680 if self.expanded else 360, area.height() - 24)
        self.setFixedSize(width, height)
        self.move(area.right() - width - 11, area.bottom() - height - 11)

    def toggle_expanded(self):
        self.expanded = not self.expanded
        self.details.setVisible(self.expanded)
        self.expand_button.setText('Згорнути подробиці ↓' if self.expanded else 'Розгорнути · графік і подробиці ↑')
        self.anchor()

    def showEvent(self, event):
        super().showEvent(event)
        self.anchor()

    def load_cache(self):
        self.schedule = None
        try:
            cached = json.loads((self.folder / f'cache-{self.group}.json').read_text(encoding='utf-8'))
            if cached['group'] == self.group:
                state_at(cached, datetime.now(KYIV))
                fresh(cached, datetime.now(KYIV))
                self.schedule = cached
                self.offline = True
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def refresh(self):
        if self.worker is not None:
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText('Оновлюємо…')
        self.settings.setEnabled(False)
        self.worker = Fetcher(self.group)
        self.worker.ready.connect(self.received)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def received(self, schedule):
        self.schedule, self.offline = schedule, False
        self.warning.setText(schedule.get('warning', ''))
        try:
            save_json(self.folder / f'cache-{self.group}.json', schedule)
        except OSError:
            self.warning.setText('Графік отримано, але не вдалося зберегти локальну копію.')
        self.tick()

    def failed(self, message):
        self.offline = True
        self.warning.setText('Немає оновлення. Показано збережений графік.' if self.schedule else 'Джерела недоступні. Повторимо через 2 хвилини.')
        self.warning.setToolTip(message)
        self.tick()

    def finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.settings.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText('Оновити графік')
        if self.quitting:
            QApplication.instance().quit()

    def tick(self):
        now = datetime.now(KYIV)
        label, target, color = state_at(self.schedule, now)
        stale = bool(self.schedule) and not fresh(self.schedule, now)
        if stale or self.offline:
            color = '#8190a8'
            label = 'Збережений графік · ' + label
        if stale:
            self.warning.setText('Дані застаріли. Розклад і відлік можуть бути неактуальними.')
        self.warning.setVisible(bool(self.warning.text()))
        self.subtitle.setText(f'Київська область  /  Черга {self.group}')
        self.status.setText(label)
        if target:
            seconds = max(0, int(target.timestamp() - now.timestamp()))
            self.countdown.setText(f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}')
            self.target.setText(f'{target:%d.%m о %H:%M} · за графіком')
        else:
            self.countdown.setText('—')
            self.target.setText('Очікуємо наступну відому подію')
        self.countdown.setStyleSheet(f'font-size: 48px; font-weight: 650; color: {color};')
        if color != self.last_color:
            self.tray.setIcon(icon(color))
            self.setWindowIcon(icon(color))
            self.last_color = color
        self.tray.setToolTip(f'Черга {self.group}\n{label}\n{self.countdown.text()}')
        for offset, widget in enumerate(self.day_labels):
            date = now.date() + timedelta(days=offset)
            title = ('Сьогодні' if offset == 0 else 'Завтра') + f' · {date:%d.%m}'
            day = next((d for d in (self.schedule or {}).get('days', []) if d['date'] == date.isoformat()), None)
            if not day or day['status'] == 'unknown':
                text = 'Графік ще не опубліковано'
            elif day['status'] == 'emergency':
                text = 'Екстрені відключення — графік не діє'
            else:
                text = '   •   '.join(f'{clock_text(a)}–{clock_text(b)}' + (' (можливо)' if kind == 'maybe' else '') for a, b, kind in day['intervals'])
                text = text or 'Відключення не заплановані'
            widget.setText(title + '\n' + text)
        if self.schedule:
            checked = timestamp(self.schedule['checked']).astimezone(KYIV)
            updated = self.schedule.get('updated')
            detail = f' · графік від {timestamp(updated).astimezone(KYIV):%d.%m %H:%M}' if updated else ''
            self.source.setText(f"{self.schedule['source']} · перевірено {checked:%d.%m %H:%M}{detail}")
        else:
            self.source.setText('GPV-UA → GitHub (резерв) · перевірка кожні 2 хвилини')

    def configure(self):
        if self.worker is not None:
            return
        dialog = Setup(self.group, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            group = dialog.combo.currentText()
            try:
                save_json(self.folder / 'settings.json', {'group': group})
            except OSError as exc:
                QMessageBox.warning(self, 'Не вдалося зберегти', str(exc))
                return
            self.group = group
            self.offline = False
            self.warning.clear()
            self.load_cache()
            self.tick()
            self.refresh()

    def reveal(self):
        self.showNormal()
        self.anchor()
        self.raise_()
        self.activateWindow()

    def activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.reveal()

    def hide_to_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()

    def closeEvent(self, event):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self.quit_app()
            event.ignore()

    def quit_app(self):
        self.quitting = True
        self.poll_timer.stop()
        self.hide()
        self.tray.hide()
        if self.worker is None:
            QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('BlackoutTracker')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        # Packaging smoke check: exercise bundled Qt, zoneinfo and widgets, then exit.
        from PySide6.QtGui import QFontDatabase
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        report = Path(sys.argv[2]).resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        Window.refresh = lambda self: None
        window = Window(report.parent, '6.1')
        setup = Setup('6.1')
        app.processEvents()
        window.grab().save(str(report.with_suffix('.png')))
        save_json(report, {'ok': True, 'frozen': bool(getattr(sys, 'frozen', False)),
                           'timezone': str(KYIV), 'queue': setup.combo.currentText(),
                           'qt_widgets': True, 'tray_available': QSystemTrayIcon.isSystemTrayAvailable()})
        window.tray.hide()
        return 0
    folder = data_directory()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        QMessageBox.critical(None, 'BlackoutTracker', f'Не вдається створити папку даних. Для portable оберіть папку з правом запису.\n{exc}')
        return 1
    lock = QLockFile(str(folder / 'app.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None, 'BlackoutTracker', 'Застосунок уже працює. Відкрийте його через іконку в треї.')
        return 0
    try:
        group = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))['group']
        if group not in GROUPS:
            raise ValueError('Invalid group')
    except (OSError, ValueError, KeyError, TypeError):
        dialog = Setup('6.1')
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        group = dialog.combo.currentText()
        save_json(folder / 'settings.json', {'group': group})
    window = Window(folder, group)
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
