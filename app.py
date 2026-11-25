import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QLockFile, QRect, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QDialogButtonBox, QSystemTrayIcon, QMenu,
    QFrame, QMessageBox, QScrollArea, QCheckBox, QSpinBox)
from preferences import load_settings
from alerts import AlertState
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
        source_note = QLabel('Графік може змінюватися й не підтверджує фактичну наявність світла.')
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


class SettingsPanel(QWidget):
    saved = Signal(dict)
    cancelled = Signal()

    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel('Налаштування')
        title.setStyleSheet('font-size: 23px; font-weight: 600;')
        layout.addWidget(title)
        layout.addWidget(QLabel('Київська область · Черга'))
        self.combo = QComboBox()
        self.combo.addItems(GROUPS)
        layout.addWidget(self.combo)
        self.always = QCheckBox('Постійно показувати оверлей')
        layout.addWidget(self.always)
        layout.addWidget(QLabel('Оновлювати API кожні:'))
        self.interval = QSpinBox()
        self.interval.setRange(1, 30)
        self.interval.setSuffix(' хв')
        self.interval.setAccessibleName('Частота оновлення API, хвилини')
        layout.addWidget(self.interval)
        self.sound = QCheckBox('Звук за 5 хвилин до відключення')
        layout.addWidget(self.sound)
        self.sound_choice = QComboBox()
        for name, key in [('Три короткі тони', 'warning'), ('Дзвінок', 'bell'), ('Сирена', 'siren')]:
            self.sound_choice.addItem(name, key)
        self.sound_choice.setAccessibleName('Звук попередження')
        layout.addWidget(self.sound_choice)
        preview = QPushButton('Прослухати')
        preview.clicked.connect(lambda: play_warning(self.sound_choice.currentData()))
        layout.addWidget(preview)
        hint = QLabel('Оверлей автоматично з’являється за 5 хвилин до відключення. Клік приховує його до наступної події. Відлік оновлюється щосекунди.')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #f6ad55;')
        layout.addWidget(self.error)
        layout.addStretch()
        row = QHBoxLayout()
        save = QPushButton('Зберегти')
        save.clicked.connect(lambda: self.saved.emit(self.values()))
        cancel = QPushButton('Скасувати')
        cancel.clicked.connect(self.cancelled.emit)
        row.addWidget(save)
        row.addWidget(cancel)
        layout.addLayout(row)
        self.load(preferences)

    def load(self, preferences):
        self.combo.setCurrentText(preferences['group'])
        self.always.setChecked(preferences['always_overlay'])
        self.interval.setValue(preferences['refresh_minutes'])
        self.sound.setChecked(preferences['sound_enabled'])
        self.sound_choice.setCurrentIndex(self.sound_choice.findData(preferences['sound_name']))
        self.error.clear()

    def values(self):
        return {'group': self.combo.currentText(), 'always_overlay': self.always.isChecked(),
                'refresh_minutes': self.interval.value(), 'sound_enabled': self.sound.isChecked(),
                'sound_name': self.sound_choice.currentData()}


def play_warning(name='warning'):
    try:
        import winsound
        name = name if name in ('warning', 'bell', 'siren') else 'warning'
        sound = Path(__file__).resolve().parent / 'assets' / (name + '.wav')
        winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except (ImportError, RuntimeError):
        QApplication.beep()


class CountdownOverlay(QWidget):
    dismissed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('BlackoutTracker · Оверлей')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.94)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(340, 180)
        self.setStyleSheet('CountdownOverlay { background: #182536; border: 1px solid #52657e; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.timer = QLabel()
        self.timer.setStyleSheet('font-size: 36px; font-weight: 650; color: #f6ad55;')
        self.hint = QLabel('Натисніть, щоб приховати')
        self.hint.setObjectName('muted')
        for widget in (self.label, self.timer, self.hint):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(widget)

    def present(self, label, countdown):
        self.label.setText(label)
        self.timer.setText(countdown)
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 15, area.top() + 16)
        if not self.isVisible():
            self.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.hide()
            self.dismissed.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


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
        self.preferences = load_settings(folder / 'settings.json', group)
        self.alerts = AlertState()
        self.overlay = CountdownOverlay()
        self.overlay.dismissed.connect(self.alerts.dismiss)
        self.schedule = None
        self.worker = None
        self.offline = False
        self.quitting = False
        self.last_color = None
        self.setWindowTitle('BlackoutTracker')
        self.expanded = False
        self.settings_open = False
        self.drawer_width = 360
        self.panel_height = 360.0
        self.drawer_reveal = 0.0
        self.motion = QVariantAnimation(self)
        self.motion.setDuration(260)
        self.motion.valueChanged.connect(self.animate_panels)
        self.motion.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.container = QWidget()
        self.container.setObjectName('shell')
        self.container.setStyleSheet('#shell { background: transparent; }')
        self.setCentralWidget(self.container)
        self.main_panel = root = QWidget(self.container)
        root.setObjectName('mainPanel')
        root.setStyleSheet('#mainPanel { background: #101722; }')
        self.drawer_clip = QWidget(self.container)
        self.drawer_clip.setObjectName('drawerClip')
        self.drawer_clip.setStyleSheet('#drawerClip { background: transparent; }')
        self.drawer = QScrollArea(self.drawer_clip)
        self.drawer.setWidgetResizable(True)
        self.drawer.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_panel = SettingsPanel(self.preferences)
        self.settings_panel.setObjectName('settingsPanel')
        self.settings_panel.setStyleSheet('#settingsPanel { background: #182536; }')
        self.drawer.setWidget(self.settings_panel)
        self.settings_panel.saved.connect(self.apply_settings)
        self.settings_panel.cancelled.connect(self.close_settings)
        self.drawer_clip.hide()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel('BlackoutTracker')
        title.setStyleSheet('font-size: 22px; font-weight: 700;')
        header.addWidget(title)
        header.addStretch()
        gear = QPushButton('…')
        gear.setAccessibleName('Налаштування')
        gear.setFixedWidth(40)
        gear.clicked.connect(self.configure)
        header.addWidget(gear)
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
        row = QHBoxLayout()
        self.refresh_button = QPushButton('Оновити графік')
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        self.settings = QPushButton('Налаштування')
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
        menu.addAction('Налаштування', self.configure)
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
        self.poll_timer.start(self.preferences['refresh_minutes'] * 60_000)
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

    def anchor(self, *_, animate=False):
        screen = self.dock_screen or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        base = min(420, area.width() - 24)
        self.drawer_width = min(360, max(0, area.width() - base - 24))
        # Keep the native translucent canvas fixed: only child widgets animate.
        # This avoids Windows resize/compositor jitter and an end-of-motion snap.
        width = base + self.drawer_width
        height = min(680, area.height() - 24)
        self.motion.stop()
        self.setGeometry(QRect(area.right() - width - 11,
                               area.bottom() - height - 11, width, height))
        self.main_start_height = self.panel_height
        self.main_end_height = min(680 if self.expanded else 360, height)
        self.drawer_start = self.drawer_reveal
        self.drawer_end = self.drawer_width if self.settings_open else 0
        if animate and self.isVisible():
            self.motion.setStartValue(0.0)
            self.motion.setEndValue(1.0)
            self.motion.start()
        else:
            self.animate_panels(1.0)

    def animate_panels(self, progress):
        self.panel_height = self.main_start_height + (self.main_end_height - self.main_start_height) * progress
        self.drawer_reveal = self.drawer_start + (self.drawer_end - self.drawer_start) * progress
        self.arrange_panels()

    def arrange_panels(self):
        if not hasattr(self, 'main_panel'):
            return
        base = min(420, self.width())
        main_height = min(self.height(), round(self.panel_height))
        edge = self.width() - base
        self.main_panel.setGeometry(edge, self.height() - main_height, base, main_height)
        visible = min(self.drawer_width, max(0, round(self.drawer_reveal)))
        drawer_height = min(620, self.height())
        self.drawer_clip.setGeometry(edge - visible, self.height() - drawer_height,
                                     visible, drawer_height)
        # Reveal the left edge first, as if the drawer were moving from under
        # the main panel. Its layout remains full-sized throughout the motion.
        self.drawer.setGeometry(0, 0, self.drawer_width, drawer_height)
        self.drawer_clip.setVisible(visible > 0)
        self.main_panel.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange_panels()

    def toggle_expanded(self):
        self.expanded = not self.expanded
        self.details.setVisible(self.expanded)
        self.expand_button.setText('Згорнути подробиці ↓' if self.expanded else 'Розгорнути · графік і подробиці ↑')
        self.anchor(animate=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.anchor()

    def load_cache(self):
        self.schedule = None
        try:
            cached = json.loads((self.folder / f'cache-{self.group}.json').read_text(encoding='utf-8'))
            if cached['group'] == self.group and cached.get('provider') == 'github':
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
        self.worker = Fetcher(self.group)
        self.worker.ready.connect(self.received)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def received(self, schedule):
        if schedule['group'] != self.group:
            return
        self.schedule, self.offline = schedule, False
        self.warning.setText(schedule.get('warning', ''))
        self.warning.setToolTip('')
        try:
            save_json(self.folder / f'cache-{self.group}.json', schedule)
        except OSError:
            self.warning.setText('Графік отримано, але не вдалося зберегти локальну копію.')
        self.tick()

    def failed(self, message):
        if self.worker is not None and self.worker.group != self.group:
            return
        self.offline = True
        self.warning.setText('Немає оновлення. Показано збережений графік.' if self.schedule else f"Джерела недоступні. Повторимо через {self.preferences['refresh_minutes']} хв.")
        self.warning.setToolTip(message)
        self.tick()

    def finished(self):
        old_group = self.worker.group
        self.worker.deleteLater()
        self.worker = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText('Оновити графік')
        if self.quitting:
            QApplication.instance().quit()
        elif old_group != self.group:
            self.refresh()

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
            self.source.setText(f"Перевірено {checked:%d.%m %H:%M}{detail}")
        else:
            self.source.setText(f"Перевірка графіка кожні {self.preferences['refresh_minutes']} хв")
        if not self.quitting:
            visible, sound = self.alerts.evaluate(self.schedule, now, self.group, self.preferences['always_overlay'])
            if visible:
                self.overlay.present(label, self.countdown.text())
            else:
                self.overlay.hide()
            if sound and self.preferences['sound_enabled']:
                play_warning(self.preferences['sound_name'])

    def configure(self):
        if self.settings_open:
            self.close_settings()
            return
        self.settings_panel.load(self.preferences)
        if not self.isVisible():
            self.reveal()
        self.settings_open = True
        self.anchor(animate=True)

    def close_settings(self):
        self.settings_open = False
        self.anchor(animate=True)

    def apply_settings(self, updated):
        try:
            save_json(self.folder / 'settings.json', updated)
        except OSError as exc:
            self.settings_panel.error.setText(f'Не вдалося зберегти: {exc}')
            return
        group_changed = updated['group'] != self.group
        if updated['always_overlay'] != self.preferences['always_overlay']:
            self.alerts.dismissed = None
        self.preferences = updated
        self.group = updated['group']
        self.poll_timer.start(updated['refresh_minutes'] * 60_000)
        if group_changed:
            self.alerts = AlertState()
            self.overlay.dismissed.disconnect()
            self.overlay.dismissed.connect(self.alerts.dismiss)
            self.offline = False
            self.warning.clear()
            self.load_cache()
        self.tick()
        if group_changed:
            self.refresh()
        self.close_settings()

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
        self.overlay.hide()
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
        setup = window.settings_panel
        app.processEvents()
        window.grab().save(str(report.with_suffix('.png')))
        save_json(report, {'ok': True, 'frozen': bool(getattr(sys, 'frozen', False)),
                           'timezone': str(KYIV), 'queue': setup.combo.currentText(),
                           'qt_widgets': True, 'sound_assets': all((Path(__file__).parent / 'assets' / (name + '.wav')).exists() for name in ('warning', 'bell', 'siren')), 'tray_available': QSystemTrayIcon.isSystemTrayAvailable()})
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
