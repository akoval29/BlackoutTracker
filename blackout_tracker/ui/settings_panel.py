import sys
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QCheckBox, QSpinBox, QSizePolicy
import blackout_tracker.windows_autostart as autostart
from blackout_tracker.ui.side_selector import SideSelector
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, groups_for, valid_group
from blackout_tracker.audio import play_warning


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

        def section(name):
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet('background: #3b4e67;')
            layout.addWidget(line)
            label = QLabel(name)
            label.setStyleSheet('color: #a6b6cd; font-size: 12px;')
            layout.addWidget(label)

        section('Графік')
        self.region_selector = SideSelector('Регіон', self)
        for key, title in REGIONS.items():
            self.region_selector.addItem(title, key)
        self.region_selector.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.region_selector.currentTextChanged.connect(self.region_selector.setToolTip)
        self.region_selector.setToolTip(self.region_selector.currentText())
        self.queue_selector = SideSelector('Черга', self)
        self.queue_selector.addItems(groups_for(DEFAULT_REGION))
        self.queue_selector.setAccessibleName('Черга')
        self.queue_selector.setFixedWidth(106)
        selection_row = QHBoxLayout()
        selection_row.setSpacing(6)
        selection_row.addWidget(self.region_selector, 1)
        selection_row.addWidget(self.queue_selector)
        layout.addLayout(selection_row)
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
        self.position = SideSelector('Розташування віджета', self)
        self.position.menu_columns = 3
        for title, key in [('Верх-ліво', 'top-left'), ('Верх-центр', 'top'), ('Верх-право', 'top-right'),
                           ('Низ-ліво', 'bottom-left'), ('Низ-центр', 'bottom'), ('Низ-право', 'bottom-right')]:
            self.position.addItem(title, key)
        layout.addWidget(self.position)
        self.position.activated.connect(lambda _: self.position_requested.emit())

        section('Сповіщення та звук')
        self.sound = QCheckBox('Звук за 5 хвилин до відключення')
        layout.addWidget(self.sound)
        self.sound_selector = SideSelector('Звук', self)
        for name, key in [('Три короткі тони', 'warning'), ('Дзвінок', 'bell'), ('Сирена', 'siren')]:
            self.sound_selector.addItem(name, key)
        self.sound_selector.setAccessibleName('Звук попередження')
        sound_row = QHBoxLayout()
        sound_row.addWidget(self.sound_selector, 1)
        preview = QPushButton('Прослухати')
        preview.clicked.connect(lambda: play_warning(self.sound_selector.currentData()))
        sound_row.addWidget(preview)
        layout.addLayout(sound_row)
        hint = QLabel('Віджет з’являється за 5 хвилин до відключення. Клік приховує його до наступної події.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #a6b6cd; font-size: 12px;')
        layout.addWidget(hint)
        section('Запуск програми')
        self.autostart = QCheckBox('Запускати разом із Windows')
        self.autostart.setToolTip('Після входу у Windows — одразу в трей. Після переміщення папки увімкніть опцію повторно. Якщо Windows вимкнула автозапуск, перевірте Диспетчер завдань.')
        layout.addWidget(self.autostart)
        self.autostart_error = QLabel()
        self.autostart_error.setWordWrap(True)
        self.autostart_error.setStyleSheet('color: #f6ad55; font-size: 12px;')
        self.autostart_error.hide()
        layout.addWidget(self.autostart_error)
        self.autostart.toggled.connect(self.change_autostart)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #f6ad55;')
        self.error.hide()
        layout.addWidget(self.error)
        layout.addStretch()
        self.load(preferences)
        self.region_selector.currentIndexChanged.connect(self.region_changed)
        for signal in (self.queue_selector.currentTextChanged, self.interval.valueChanged,
                       self.position.currentIndexChanged, self.topmost.toggled, self.sound.toggled, self.sound_selector.currentIndexChanged):
            signal.connect(self.changed)

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
            self.sound.setChecked(preferences['sound_enabled'])
            self.sound_selector.setCurrentIndex(self.sound_selector.findData(preferences['sound_name']))
            self.error.clear()
            self.error.hide()
        finally:
            self.loading = False

    def values(self):
        return {'region': self.region_selector.currentData(), 'group': self.queue_selector.currentText(), 'overlay_topmost': self.topmost.isChecked(),
                'refresh_minutes': self.interval.value(), 'sound_enabled': self.sound.isChecked(),
                'sound_name': self.sound_selector.currentData(), 'overlay_position': self.position.currentData()}

