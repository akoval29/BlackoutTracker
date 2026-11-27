from blackout_tracker.ui.theme import GRADIENT_DIVIDER_STYLE
import sys
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QCheckBox, QSpinBox, QSizePolicy
import blackout_tracker.windows_autostart as autostart
from blackout_tracker.ui.side_selector import SideSelector
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, groups_for, valid_group
from blackout_tracker.audio import play_warning
from blackout_tracker.version import VERSION


class SettingsPanel(QWidget):
    saved = Signal(dict)
    position_requested = Signal()

    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        self.loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)
        title = QLabel('Налаштування')
        title.setStyleSheet('font-size: 20px; font-weight: 600;')
        layout.addWidget(title)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(GRADIENT_DIVIDER_STYLE)
        layout.addWidget(line)
        self.root_layout = layout
        self.columns = QGridLayout()
        self.columns.setHorizontalSpacing(14)
        self.columns.setVerticalSpacing(14)
        self.section_cards = {}
        self.wide_columns = None
        self.root_layout.addLayout(self.columns)

        def section(name, order):
            card = QFrame()
            card.setObjectName('settingsSection')
            card.setStyleSheet('#settingsSection { background: #304158; border: 1px solid #4a607c; border-radius: 10px; }')
            body = QVBoxLayout(card)
            body.setContentsMargins(12, 12, 12, 12)
            body.setSpacing(10)
            body.setAlignment(Qt.AlignmentFlag.AlignTop)
            label = QLabel(name)
            label.setStyleSheet('color: #e4edf9; font-size: 14px; font-weight: 600;')
            body.addWidget(label)
            self.section_cards[order] = card
            self.columns.addWidget(card, order, 0)
            return body

        layout = section('Графік відключень', 0)
        self.region_selector = SideSelector('Регіон', self)
        for key, title in REGIONS.items():
            self.region_selector.addItem(title, key)
        self.region_selector.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.region_selector.currentTextChanged.connect(self.region_selector.setToolTip)
        self.region_selector.setToolTip(self.region_selector.currentText())
        self.queue_selector = SideSelector('Черга', self)
        self.queue_selector.addItems(groups_for(DEFAULT_REGION))
        self.queue_selector.setAccessibleName('Черга')
        self.queue_selector.setFixedWidth(90)
        selection_row = QHBoxLayout()
        selection_row.setSpacing(6)
        selection_row.addWidget(self.region_selector, 1)
        selection_row.addWidget(self.queue_selector)
        layout.addLayout(selection_row)
        row = QHBoxLayout()
        row.setSpacing(4)
        refresh_label = QLabel('Оновлювати графік кожні')
        refresh_label.setStyleSheet('font-size: 12px;')
        row.addWidget(refresh_label)
        self.interval = QSpinBox()
        self.interval.setRange(1, 30)
        self.interval.setToolTip('Інтервал у хвилинах: введіть число або змініть стрілками клавіатури.')
        self.interval.setSuffix(' хв')
        self.interval.setKeyboardTracking(False)
        self.interval.setFixedWidth(52)
        self.interval.setStyleSheet('font-size: 12px;')
        row.addWidget(self.interval)
        self.refresh_button = QPushButton('Зараз')
        self.refresh_button.setFixedWidth(88)
        checkmark = QPixmap(16, 16)
        checkmark.fill(Qt.GlobalColor.transparent)
        painter = QPainter(checkmark)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#5ee0af'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(3, 8, 6, 11)
        painter.drawLine(6, 11, 13, 4)
        painter.end()
        self.refresh_success_icon = QIcon(checkmark)
        self.refresh_button.setIconSize(QSize(16, 16))
        self.set_refresh_status('idle')
        row.addWidget(self.refresh_button)
        layout.addLayout(row)

        layout = section('Віджет', 2)
        self.topmost = QCheckBox('Показувати віджет поверх усіх вікон')
        layout.addWidget(self.topmost)
        self.position = SideSelector('Розташування віджета', self)
        self.position.menu_columns = 3
        for title, key in [('Верх-ліво', 'top-left'), ('Верх-центр', 'top'), ('Верх-право', 'top-right'),
                           ('Низ-ліво', 'bottom-left'), ('Низ-центр', 'bottom'), ('Низ-право', 'bottom-right')]:
            self.position.addItem(title, key)
        layout.addWidget(self.position)
        self.position.activated.connect(lambda _: self.position_requested.emit())
        widget_hint = QLabel('Автоматично з’являється за 5 хвилин. Клік на таймері приховує його.')
        widget_hint.setWordWrap(True)
        widget_hint.setStyleSheet('color: #c0ccdc; font-size: 12px;')
        layout.addWidget(widget_hint)

        layout = section('Звукові попередження', 1)
        self.notify_10 = QCheckBox('За 10 хвилин')
        self.notify_5 = QCheckBox('За 5 хвилин')
        for checkbox, minutes in ((self.notify_10, 10), (self.notify_5, 5)):
            sound_row = QHBoxLayout()
            sound_row.addWidget(checkbox, 1)
            preview = QPushButton('Прослухати')
            preview.setStyleSheet('font-size: 12px; padding: 7px;')
            preview.setFixedWidth(96)
            preview.clicked.connect(lambda checked=False, value=minutes: play_warning(value))
            sound_row.addWidget(preview)
            layout.addLayout(sound_row)
        hint = QLabel('Сирена → голосове повідомлення. Оберіть один або обидва інтервали. Жодного — без звуку.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #c0ccdc; font-size: 12px;')
        layout.addWidget(hint)
        layout = section('Запуск програми', 3)
        self.autostart = QCheckBox('Запускати разом із Windows')
        self.autostart.setToolTip('Після входу у Windows — одразу в трей. Після переміщення папки увімкніть опцію повторно. Якщо Windows вимкнула автозапуск, перевірте Диспетчер завдань.')
        layout.addWidget(self.autostart)
        self.autostart_error = QLabel()
        self.autostart_error.setWordWrap(True)
        self.autostart_error.setStyleSheet('color: #f6ad55; font-size: 12px;')
        self.autostart_error.hide()
        layout.addWidget(self.autostart_error)
        self.autostart.toggled.connect(self.change_autostart)
        startup_hint = QLabel('Після входу у Windows програма працюватиме в треї.')
        startup_hint.setWordWrap(True)
        startup_hint.setStyleSheet('color: #c0ccdc; font-size: 12px;')
        layout.addWidget(startup_hint)
        layout = section('Оновлення програми', 4)
        self.auto_updates = QCheckBox('Автоматично перевіряти оновлення')
        self.auto_updates.setToolTip('Перевірка GitHub при запуску та кожні 6 годин. Завантаження — лише після вашого кліку.')
        layout.addWidget(self.auto_updates)
        self.update_status = QLabel(f'Версія {VERSION}. Завантаження й перезапуск — лише після вашого кліку.')
        self.update_status.setWordWrap(True)
        self.update_status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.update_status)
        self.update_notes = QLabel()
        self.update_notes.setWordWrap(True)
        self.update_notes.setTextFormat(Qt.TextFormat.PlainText)
        self.update_notes.hide()
        layout.addWidget(self.update_notes)
        self.update_button = QPushButton('Перевірити оновлення')
        layout.addWidget(self.update_button)
        layout = self.root_layout
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #f6ad55;')
        self.error.hide()
        layout.addWidget(self.error)
        layout.addStretch()
        self.load(preferences)
        self.region_selector.currentIndexChanged.connect(self.region_changed)
        for signal in (self.queue_selector.currentTextChanged, self.interval.valueChanged,
                       self.position.currentIndexChanged, self.topmost.toggled, self.notify_5.toggled, self.notify_10.toggled, self.auto_updates.toggled):
            signal.connect(self.changed)

    def configure_columns(self, width):
        wide = width >= 680
        if wide == self.wide_columns:
            return
        self.wide_columns = wide
        for order, card in self.section_cards.items():
            self.columns.removeWidget(card)
            self.columns.addWidget(card, order // 2 if wide else order, order % 2 if wide else 0)
        self.columns.setColumnStretch(0, 1)
        self.columns.setColumnStretch(1, 1 if wide else 0)
        self.root_layout.invalidate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.configure_columns(event.size().width())

    def set_refresh_status(self, status):
        text, color = {
            'idle': ('Зараз', '#f2f6fc'),
            'loading': ('Оновлення…', '#c0ccdc'),
            'success': ('Оновлено', '#5ee0af'),
            'error': ('Помилка', '#f87171'),
        }[status]
        self.refresh_button.setText(text)
        self.refresh_button.setIcon(self.refresh_success_icon if status == 'success' else QIcon())
        self.refresh_button.setStyleSheet(f'font-size: 12px; padding: 9px 4px; color: {color};')
        self.refresh_button.setToolTip('Оновити графік зараз')

    def refresh_autostart(self):
        self.autostart.blockSignals(True)
        try:
            self.autostart.setChecked(autostart.is_enabled())
            self.autostart.setEnabled(sys.platform == 'win32')
            self.autostart_error.hide()
        except OSError as exc:
            self.autostart.setEnabled(False)
            self.autostart_error.setText(f'Не вдалося перевірити автозапуск: {exc}')
            self.autostart_error.show()
        finally:
            self.autostart.blockSignals(False)

    def change_autostart(self, enabled):
        if self.loading:
            return
        try:
            autostart.set_enabled(enabled)
        except OSError as exc:
            self.refresh_autostart()
            self.autostart_error.setText(f'Не вдалося змінити автозапуск: {exc}')
            self.autostart_error.show()
        else:
            self.refresh_autostart()

    def region_changed(self, *_):
        group = self.queue_selector.currentText()
        region = self.region_selector.currentData()
        self.loading = True
        try:
            self.queue_selector.clear()
            self.queue_selector.addItems(groups_for(region))
            self.queue_selector.setCurrentText(valid_group(region, group))
        finally:
            self.loading = False
        self.changed()

    def changed(self, *_):
        if not self.loading:
            self.saved.emit(self.values())

    def load(self, preferences):
        self.refresh_autostart()
        self.loading = True
        try:
            self.region_selector.blockSignals(True)
            self.region_selector.setCurrentIndex(self.region_selector.findData(preferences['region']))
            self.region_selector.blockSignals(False)
            self.queue_selector.clear()
            self.queue_selector.addItems(groups_for(preferences['region']))
            self.queue_selector.setCurrentText(preferences['group'])
            self.topmost.setChecked(preferences['overlay_topmost'])
            self.position.setCurrentIndex(self.position.findData(preferences['overlay_position']))
            self.interval.setValue(preferences['refresh_minutes'])
            self.notify_5.setChecked(preferences['notify_5_minutes'])
            self.notify_10.setChecked(preferences['notify_10_minutes'])
            self.auto_updates.setChecked(preferences.get('check_updates', True))
            self.error.clear()
            self.error.hide()
        finally:
            self.loading = False

    def values(self):
        return {'region': self.region_selector.currentData(), 'group': self.queue_selector.currentText(), 'overlay_topmost': self.topmost.isChecked(),
                'refresh_minutes': self.interval.value(), 'notify_5_minutes': self.notify_5.isChecked(),
                'notify_10_minutes': self.notify_10.isChecked(), 'overlay_position': self.position.currentData(),
                'check_updates': self.auto_updates.isChecked()}

