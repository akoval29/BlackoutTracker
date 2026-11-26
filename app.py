import json
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QLockFile, QRect, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QDialogButtonBox, QSystemTrayIcon, QMenu,
    QFrame, QMessageBox, QScrollArea, QCheckBox, QSpinBox)
from preferences import load_settings
from alerts import AlertState
from schedule_chart import ScheduleChart
from ripple import Ripple
from side_select import SideSelect
from regions import DEFAULT_REGION, REGIONS, groups_for, valid_group
from core import KYIV, fetch_schedule, state_at, fresh, timestamp

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
        self.region_choice = QComboBox()
        for key, title in REGIONS.items():
            self.region_choice.addItem(title, key)
        layout.addWidget(self.region_choice)
        note = QLabel('Регіон і чергу можна змінити будь-коли в налаштуваннях.')
        note.setObjectName('muted')
        layout.addWidget(note)
        source_note = QLabel('Графік може змінюватися й не підтверджує фактичну наявність світла.')
        source_note.setWordWrap(True)
        source_note.setObjectName('muted')
        layout.addWidget(source_note)
        self.combo = QComboBox()
        self.combo.addItems(groups_for(DEFAULT_REGION))
        self.combo.setCurrentText(group)
        self.combo.setAccessibleName('Черга відключень')
        layout.addWidget(self.combo)
        self.region_choice.currentIndexChanged.connect(self.update_groups)
        buttons = QDialogButtonBox()
        buttons.addButton('Зберегти', QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton('Скасувати', QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_groups(self, *_):
        group = self.combo.currentText()
        region = self.region_choice.currentData()
        self.combo.clear()
        self.combo.addItems(groups_for(region))
        self.combo.setCurrentText(valid_group(region, group))


class SettingsPanel(QWidget):
    saved = Signal(dict)

    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        self.loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)
        title = QLabel('Налаштування')
        title.setStyleSheet('font-size: 20px; font-weight: 600;')
        layout.addWidget(title)

        def section(name):
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet('background: #3b4e67;')
            layout.addWidget(line)
            label = QLabel(name)
            label.setStyleSheet('color: #a6b6cd; font-size: 12px;')
            layout.addWidget(label)

        section('Графік')
        self.region_choice = SideSelect('Регіон', self)
        for key, title in REGIONS.items():
            self.region_choice.addItem(title, key)
        layout.addWidget(self.region_choice)
        self.combo = SideSelect('Черга', self)
        self.combo.addItems(groups_for(DEFAULT_REGION))
        self.combo.setAccessibleName('Черга')
        layout.addWidget(self.combo)
        row = QHBoxLayout()
        row.addWidget(QLabel('Оновлювати кожні:'))
        self.interval = QSpinBox()
        self.interval.setRange(1, 30)
        self.interval.setSuffix(' хв')
        self.interval.setKeyboardTracking(False)
        row.addWidget(self.interval)
        layout.addLayout(row)
        self.refresh_button = QPushButton('Оновити графік відключень')
        layout.addWidget(self.refresh_button)

        section('Віджет')
        self.topmost = QCheckBox('Показувати віджет поверх усіх вікон')
        layout.addWidget(self.topmost)
        self.position = SideSelect('Розташування віджета', self)
        for title, key in [('Верх', 'top'), ('Верх-право', 'top-right'), ('Верх-ліво', 'top-left'),
                           ('Низ-право', 'bottom-right'), ('Низ-ліво', 'bottom-left')]:
            self.position.addItem(title, key)
        layout.addWidget(self.position)

        section('Сповіщення та звук')
        self.sound = QCheckBox('Звук за 5 хвилин до відключення')
        layout.addWidget(self.sound)
        self.sound_choice = SideSelect('Звук', self)
        for name, key in [('Три короткі тони', 'warning'), ('Дзвінок', 'bell'), ('Сирена', 'siren')]:
            self.sound_choice.addItem(name, key)
        self.sound_choice.setAccessibleName('Звук попередження')
        sound_row = QHBoxLayout()
        sound_row.addWidget(self.sound_choice, 1)
        preview = QPushButton('Прослухати')
        preview.clicked.connect(lambda: play_warning(self.sound_choice.currentData()))
        sound_row.addWidget(preview)
        layout.addLayout(sound_row)
        hint = QLabel('Віджет з’являється за 5 хвилин до відключення. Клік приховує його до наступної події.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #a6b6cd; font-size: 12px;')
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #f6ad55;')
        self.error.hide()
        layout.addWidget(self.error)
        layout.addStretch()
        self.load(preferences)
        self.region_choice.currentIndexChanged.connect(self.region_changed)
        for signal in (self.combo.currentTextChanged, self.interval.valueChanged,
                       self.position.currentIndexChanged, self.topmost.toggled, self.sound.toggled, self.sound_choice.currentIndexChanged):
            signal.connect(self.changed)

    def region_changed(self, *_):
        group = self.combo.currentText()
        region = self.region_choice.currentData()
        self.loading = True
        try:
            self.combo.clear()
            self.combo.addItems(groups_for(region))
            self.combo.setCurrentText(valid_group(region, group))
        finally:
            self.loading = False
        self.changed()

    def changed(self, *_):
        if not self.loading:
            self.saved.emit(self.values())

    def load(self, preferences):
        self.loading = True
        try:
            self.region_choice.blockSignals(True)
            self.region_choice.setCurrentIndex(self.region_choice.findData(preferences['region']))
            self.region_choice.blockSignals(False)
            self.combo.clear()
            self.combo.addItems(groups_for(preferences['region']))
            self.combo.setCurrentText(preferences['group'])
            self.topmost.setChecked(preferences['overlay_topmost'])
            self.position.setCurrentIndex(self.position.findData(preferences['overlay_position']))
            self.interval.setValue(preferences['refresh_minutes'])
            self.sound.setChecked(preferences['sound_enabled'])
            self.sound_choice.setCurrentIndex(self.sound_choice.findData(preferences['sound_name']))
            self.error.clear()
            self.error.hide()
        finally:
            self.loading = False

    def values(self):
        return {'region': self.region_choice.currentData(), 'group': self.combo.currentText(), 'overlay_topmost': self.topmost.isChecked(),
                'refresh_minutes': self.interval.value(), 'sound_enabled': self.sound.isChecked(),
                'sound_name': self.sound_choice.currentData(), 'overlay_position': self.position.currentData()}


def play_warning(name='warning'):
    try:
        import winsound
        name = name if name in ('warning', 'bell', 'siren') else 'warning'
        sound = Path(__file__).resolve().parent / 'assets' / (name + '.wav')
        winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except (ImportError, RuntimeError):
        QApplication.beep()


class AnimatedTimerLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.scale = 1.0
        self.ink = QColor('#5ee0af')

    def paintEvent(self, event):
        if self.scale <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(self.ink)
        painter.setFont(self.font())
        center = self.rect().center()
        painter.translate(center)
        painter.scale(self.scale, self.scale)
        painter.translate(-center)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class CountdownOverlay(QWidget):
    dismissed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('BlackoutTracker · Оверлей')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(90, 23)
        self.setStyleSheet('CountdownOverlay { background: transparent; border: none; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        self.timer = AnimatedTimerLabel('—')
        self.timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.timer)
        self.ripple = Ripple(self)
        self.last_position = None
        self.text_motion = QVariantAnimation(self)
        self.text_motion.setDuration(420)
        self.text_motion.setStartValue(0.0)
        self.text_motion.setEndValue(1.0)
        self.text_motion.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.text_motion.valueChanged.connect(self.animate_text)

    def animate_text(self, scale):
        self.timer.scale = scale
        self.timer.update()

    def present(self, label, countdown, color, position='top-right'):
        animate = not self.isVisible() or position != self.last_position
        self.last_position = position
        self.timer.setText(countdown)
        self.timer.ink = QColor(color)
        self.timer.setStyleSheet(f'font-size: 15px; font-weight: 650; color: {color};')
        self.timer.ensurePolished()
        metrics = self.timer.fontMetrics()
        # Reserve equal digit widths so ticking cannot move or resize the timer.
        digit_width = max(metrics.horizontalAdvance(str(digit)) for digit in range(10))
        width = digit_width * max(6, len(countdown.replace(':', ''))) + metrics.horizontalAdvance('::')
        self.setFixedSize(width + 2, metrics.height() + 2)
        self.setAccessibleName(f'{label}: {countdown}')
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            right = area.right() - self.width() + 1
            bottom = area.bottom() - self.height() + 1
            # Reserve the title-bar controls at the top-right of maximized windows.
            positions = {
                'top': (area.left() + (area.width() - self.width()) // 2, area.top()),
                'top-right': (right, min(bottom, area.top() + 40)),
                'top-left': (area.left(), area.top()),
                'bottom-right': (right, bottom),
                'bottom-left': (area.left(), bottom),
            }
            self.move(*positions.get(position, positions['top-right']))
        if not self.isVisible():
            self.show()
        if animate:
            self.text_motion.stop()
            self.animate_text(0.0)
            self.text_motion.start()
            self.ripple.start(self.geometry().center(), color,
                              bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))

    def hideEvent(self, event):
        self.ripple.stop()
        self.text_motion.stop()
        super().hideEvent(event)

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

    def __init__(self, group, region=DEFAULT_REGION):
        super().__init__()
        self.group, self.region = group, region

    def run(self):
        try:
            self.ready.emit(fetch_schedule(self.group, self.region))
        except Exception as exc:
            self.failed.emit(str(exc))


class Window(QMainWindow):
    def __init__(self, folder, group):
        super().__init__()
        self.folder, self.group = folder, group
        self.preferences = load_settings(folder / 'settings.json', group)
        self.region = self.preferences['region']
        self.group = self.preferences['group']
        self.alerts = AlertState()
        self.overlay = CountdownOverlay()
        self.overlay.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.preferences['overlay_topmost'])
        self.overlay.dismissed.connect(self.dismiss_overlay)
        self.manual_overlay = False
        self.schedule = None
        self.worker = None
        self.offline = False
        self.quitting = False
        self.last_color = None
        self.setWindowTitle('BlackoutTracker')
        self.expanded = False
        self.settings_open = False
        self.drawer_width = 360
        self.panel_height = 290.0
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
        self.drawer_clip.hide()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel('BlackoutTracker')
        title.setStyleSheet('font-size: 20px; font-weight: 700;')
        header.addWidget(title)
        header.addStretch()
        self.widget_button = QPushButton('Віджет: викл')
        self.widget_button.setStyleSheet('font-size: 12px; padding: 9px 7px;')
        self.widget_button.clicked.connect(self.toggle_overlay)
        header.addWidget(self.widget_button)
        hide = QPushButton('×')
        hide.setAccessibleName('Сховати у трей')
        hide.setToolTip('Сховати у трей')
        hide.setFixedWidth(40)
        hide.clicked.connect(self.hide_to_tray)
        header.addWidget(hide)
        layout.addLayout(header)
        self.subtitle = QLabel()
        self.subtitle.setObjectName('muted')
        card = QFrame()
        card.setObjectName('card')
        cardlayout = QVBoxLayout(card)
        cardlayout.setContentsMargins(12, 8, 12, 8)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cardlayout.addWidget(self.subtitle)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet('background: #3b4e67; border: none;')
        cardlayout.addWidget(divider)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.countdown = QLabel('—')
        self.countdown.setStyleSheet('font-size: 40px; font-weight: 650;')
        self.target = QLabel()
        self.target.setObjectName('muted')
        for label in (self.status, self.countdown, self.target):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        details_layout.setSpacing(6)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details.setWidget(details_body)
        self.chart = ScheduleChart()
        details_layout.addWidget(self.chart)
        self.source = QLabel()
        self.source.setWordWrap(True)
        self.source.setObjectName('muted')
        details_layout.addWidget(self.source)
        row = QHBoxLayout()
        self.refresh_button = self.settings_panel.refresh_button
        self.refresh_button.clicked.connect(self.refresh)
        self.settings = QPushButton('Налаштування')
        self.settings.clicked.connect(self.configure)
        row.addWidget(self.settings)
        details_layout.addLayout(row)
        footer = QLabel('Час за Києвом · План, не фактичний стан мережі')
        footer.setWordWrap(True)
        footer.setObjectName('muted')
        footer.setStyleSheet('font-size: 12px;')
        details_layout.addWidget(footer)

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
        base = min(420, area.width())
        self.drawer_width = min(360, max(0, area.width() - base))
        # Keep the native translucent canvas fixed: only child widgets animate.
        # This avoids Windows resize/compositor jitter and an end-of-motion snap.
        width = base + self.drawer_width
        height = min(620, area.height())
        self.motion.stop()
        self.setGeometry(QRect(area.right() - width + 1,
                               area.bottom() - height + 1, width, height))
        self.main_start_height = self.panel_height
        self.main_end_height = min(560 if self.expanded else 290, height)
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
        drawer_height = main_height
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
        if not self.expanded:
            self.settings_open = False
        self.details.setVisible(self.expanded)
        self.expand_button.setText('Згорнути подробиці ↓' if self.expanded else 'Розгорнути · графік і подробиці ↑')
        self.anchor(animate=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.anchor()

    def load_cache(self):
        self.schedule = None
        try:
            path = self.folder / f'cache-{self.region}-{self.group}.json'
            if not path.exists() and self.region == DEFAULT_REGION:
                path = self.folder / f'cache-{self.group}.json'
            cached = json.loads(path.read_text(encoding='utf-8'))
            if cached['group'] == self.group and cached.get('region', DEFAULT_REGION) == self.region and cached.get('provider') == 'github':
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
        self.worker = Fetcher(self.group, self.region)
        self.worker.ready.connect(self.received)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def received(self, schedule):
        if (schedule.get('region', DEFAULT_REGION), schedule['group']) != (self.region, self.group):
            return
        self.schedule, self.offline = schedule, False
        self.warning.setText(schedule.get('warning', ''))
        self.warning.setToolTip('')
        try:
            save_json(self.folder / f'cache-{self.region}-{self.group}.json', schedule)
        except OSError:
            self.warning.setText('Графік отримано, але не вдалося зберегти локальну копію.')
        self.tick()

    def failed(self, message):
        if self.worker is not None and (self.worker.region, self.worker.group) != (self.region, self.group):
            return
        self.offline = True
        self.warning.setText('Немає оновлення. Показано збережений графік.' if self.schedule else f"Джерела недоступні. Повторимо через {self.preferences['refresh_minutes']} хв.")
        self.warning.setToolTip(message)
        self.tick()

    def finished(self):
        old_selection = (self.worker.region, self.worker.group)
        self.worker.deleteLater()
        self.worker = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText('Оновити графік відключень')
        if self.quitting:
            QApplication.instance().quit()
        elif old_selection != (self.region, self.group):
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
        self.subtitle.setText(f'{REGIONS[self.region]}  /  Черга {self.group}')
        self.status.setText(label)
        if target:
            seconds = max(0, int(target.timestamp() - now.timestamp()))
            self.countdown.setText(f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}')
            self.target.setText(f'{target:%d.%m о %H:%M} · за графіком')
        else:
            self.countdown.setText('—')
            self.target.setText('Очікуємо наступну відому подію')
        self.countdown.setStyleSheet(f'font-size: 40px; font-weight: 650; color: {color};')
        if color != self.last_color:
            self.tray.setIcon(icon(color))
            self.setWindowIcon(icon(color))
            self.last_color = color
        self.tray.setToolTip(f'{REGIONS[self.region]} · Черга {self.group}\n{label}\n{self.countdown.text()}')
        self.chart.set_schedule(self.schedule, now)
        if self.schedule:
            checked = timestamp(self.schedule['checked']).astimezone(KYIV)
            updated = self.schedule.get('updated')
            detail = f' · графік від {timestamp(updated).astimezone(KYIV):%d.%m %H:%M}' if updated else ''
            self.source.setText(f"Перевірено {checked:%d.%m %H:%M}{detail}")
        else:
            self.source.setText(f"Перевірка графіка кожні {self.preferences['refresh_minutes']} хв")
        if not self.quitting:
            visible, sound = self.alerts.evaluate(self.schedule, now, self.group, self.manual_overlay)
            if visible:
                self.overlay.present(label, self.countdown.text(), color, self.preferences['overlay_position'])
            else:
                self.overlay.hide()
            self.sync_widget_button()
            if sound and self.preferences['sound_enabled']:
                play_warning(self.preferences['sound_name'])

    def sync_widget_button(self):
        visible = self.overlay.isVisible()
        self.widget_button.setText('Віджет: вкл' if visible else 'Віджет: викл')
        self.widget_button.setToolTip('Приховати віджет' if visible else 'Показати віджет')

    def dismiss_overlay(self):
        self.manual_overlay = False
        self.alerts.dismiss()
        self.sync_widget_button()

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.dismiss_overlay()
        else:
            self.manual_overlay = True
            self.alerts.dismissed = None
            self.tick()

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
            self.settings_panel.error.show()
            return
        group_changed = (updated['region'], updated['group']) != (self.region, self.group)
        self.settings_panel.error.clear()
        self.settings_panel.error.hide()
        if updated['overlay_topmost'] != self.preferences['overlay_topmost']:
            self.overlay.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, updated['overlay_topmost'])
        self.preferences = updated
        self.group = updated['group']
        self.region = updated['region']
        self.poll_timer.start(updated['refresh_minutes'] * 60_000)
        if group_changed:
            self.alerts = AlertState()
            self.overlay.dismissed.disconnect()
            self.overlay.dismissed.connect(self.dismiss_overlay)
            self.offline = False
            self.warning.clear()
            self.load_cache()
        self.tick()
        if group_changed:
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
        stored = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))
        group = stored['group']
        if stored.get('region', DEFAULT_REGION) not in REGIONS or group not in groups_for(stored.get('region', DEFAULT_REGION)):
            raise ValueError('Invalid group')
    except (OSError, ValueError, KeyError, TypeError):
        dialog = Setup('6.1')
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        group = dialog.combo.currentText()
        save_json(folder / 'settings.json', {'region': dialog.region_choice.currentData(), 'group': group})
    window = Window(folder, group)
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
