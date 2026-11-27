from blackout_tracker.ui.theme import GRADIENT_DIVIDER_STYLE
import sys
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QCheckBox, QSpinBox, QSizePolicy, QTabBar, QButtonGroup
import blackout_tracker.windows_autostart as autostart
from blackout_tracker.ui.side_selector import SideSelector
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, groups_for, valid_group
from blackout_tracker.audio import play_warning, play_message
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
        header = QHBoxLayout()
        header.setSpacing(14)
        header.addWidget(title)
        self.tabs = QTabBar()
        self.tabs.setAccessibleName('Розділи налаштувань')
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDrawBase(False)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.tabs.setStyleSheet(
            'QTabBar { background: transparent; }'
            'QTabBar::tab { color: #c0ccdc; background: transparent; font-size: 12px; '
            'padding: 8px 10px; border-bottom: 2px solid transparent; }'
            'QTabBar::tab:selected { color: #86e9cf; background: #304158; border-bottom-color: #86e9cf; }'
            'QTabBar::tab:hover { background: #34465e; }')
        for name in ('Графік', 'Звук', 'Віджет', 'Запуск', 'Оновлення', 'Про нас'):
            self.tabs.addTab(name)
        header.addWidget(self.tabs, 1)
        layout.addLayout(header)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(GRADIENT_DIVIDER_STYLE)
        layout.addWidget(line)
        self.root_layout = layout
        self.section_cards = {}

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
            self.root_layout.addWidget(card)
            card.setVisible(order == self.tabs.currentIndex())
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
        language_row = QHBoxLayout()
        self.audio_language_group = QButtonGroup(self)
        self.audio_language_group.setExclusive(True)
        self.audio_language_buttons = {}
        for label, language in [('Українська', 'ua'), ('English', 'en'), ('Deutsch', 'de')]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty('language', language)
            button.setAccessibleName(f'Мова аудіо: {label}')
            button.setStyleSheet(
                'QPushButton { font-size: 12px; padding: 8px 4px; border: 1px solid #637a94; border-radius: 6px; }'
                'QPushButton:checked { background: #245b52; color: #adffe8; border: 2px solid #72e0bd; font-weight: 600; }')
            self.audio_language_group.addButton(button)
            self.audio_language_buttons[language] = button
            language_row.addWidget(button)
        layout.addLayout(language_row)
        self.notify_10 = QCheckBox('За 10 хвилин')
        self.notify_5 = QCheckBox('За 5 хвилин')
        self.audio_previews = {}
        for checkbox, minutes in ((self.notify_10, 10), (self.notify_5, 5)):
            sound_row = QHBoxLayout()
            sound_row.addWidget(checkbox, 1)
            preview = QPushButton('Прослухати')
            preview.setStyleSheet('font-size: 12px; padding: 7px;')
            preview.setFixedWidth(96)
            preview.clicked.connect(lambda checked=False, value=minutes: play_warning(value, self.selected_audio_language()))
            self.audio_previews[minutes] = preview
            sound_row.addWidget(preview)
            layout.addLayout(sound_row)
        hint = QLabel('«Увага!» → голосове повідомлення. Оберіть один або обидва інтервали. Жодного — без звуку.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #c0ccdc; font-size: 12px;')
        layout.addWidget(hint)
        examples_title = QLabel('Інші приклади · лише прослуховування')
        examples_title.setStyleSheet('color: #c0ccdc; font-size: 12px;')
        layout.addWidget(examples_title)
        self.message_previews = {}
        for label, message_id in [('Зміна графіка', 'power.schedule_changed'),
                                  ('Повітряна тривога', 'alert.air_raid'),
                                  ('Програму оновлено', 'app.updated')]:
            example_row = QHBoxLayout()
            example_row.addWidget(QLabel(label), 1)
            preview = QPushButton('Прослухати')
            preview.setStyleSheet('font-size: 12px; padding: 7px;')
            preview.setFixedWidth(96)
            preview.clicked.connect(lambda checked=False, ident=message_id: self.preview_message(ident))
            self.message_previews[message_id] = preview
            example_row.addWidget(preview)
            layout.addLayout(example_row)
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
        layout = section(f'BlackoutTracker · {VERSION}', 5)
        about = QLabel(
            '<p><b>Безкоштовний помічник для планування дня зі світлом.</b><br>'
            'Portable-застосунок для Windows із відкритим кодом. Користування безкоштовне; '
            'встановлювати Python чи інші компоненти не потрібно.</p>'
            '<p><b>Проєкт та автор</b><br>'
            'BlackoutTracker розвиває <a href="https://github.com/akoval29">akoval29</a>. '
            'Код і нові версії доступні в '
            '<a href="https://github.com/akoval29/BlackoutTracker">репозиторії на GitHub</a>. '
            'Є ідея або знайшли помилку? '
            '<a href="https://github.com/akoval29/BlackoutTracker/issues">Напишіть у розділі Issues</a>.</p>'
            '<p><b>Як це працює</b><br>'
            'Оберіть регіон і чергу: програма періодично перевіряє графік, показує відлік '
            'до наступної події та зберігає зміни в журналі. Є віджет і звукові попередження. '
            'Після закриття вікна програма продовжує працювати в треї. '
            'Усі години — за Києвом; налаштування, кеш і журнал зберігаються локально.</p>'
            '<p><b>Джерело даних і подяка</b><br>'
            'Графіки надходять із відкритого проєкту '
            '<a href="https://github.com/uapowerguardkit/outage-data-ua">outage-data-ua</a> '
            '(раніше Baskerville42/outage-data-ua). Він збирає дані з публічних сторінок постачальників. '
            'Дякуємо Alexander Tartmin, зазначеному в '
            '<a href="https://github.com/uapowerguardkit/outage-data-ua/blob/main/LICENSE">ліцензії проєкту</a>, '
            'та всім його учасникам за відкриті дані.</p>'
            '<p><b>Що варто знати</b><br>'
            'Графік — це план, а не вимірювання наявності електрики. Під час екстрених відключень '
            'він може не діяти. Без інтернету показується збережений графік; застарілі дані позначаються. '
            'Знак ∞ означає, що час наступної події невідомий, а не гарантію безперервного світла.</p>')
        about.setWordWrap(True)
        about.setTextFormat(Qt.TextFormat.RichText)
        about.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        about.setOpenExternalLinks(True)
        about.setStyleSheet('font-size: 13px; color: #d5dfed;')
        # Keep links readable on the dark panel without changing other labels.
        about.setText(about.text().replace('<a href=', '<a style="color: #86e9cf;" href='))
        layout.addWidget(about)
        layout = self.root_layout
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #f6ad55;')
        self.error.hide()
        layout.addWidget(self.error)
        layout.addStretch()
        self.tabs.currentChanged.connect(self.select_tab)
        self.load(preferences)
        self.region_selector.currentIndexChanged.connect(self.region_changed)
        for signal in (self.queue_selector.currentTextChanged, self.interval.valueChanged,
                       self.position.currentIndexChanged, self.topmost.toggled, self.notify_5.toggled, self.notify_10.toggled, self.auto_updates.toggled):
            signal.connect(self.changed)
        self.audio_language_group.buttonToggled.connect(lambda _button, checked: self.changed() if checked else None)

    def selected_audio_language(self):
        button = self.audio_language_group.checkedButton()
        return button.property('language') if button else 'ua'

    def preview_message(self, message_id):
        try:
            play_message(message_id, self.selected_audio_language())
        except (OSError, ValueError, KeyError, RuntimeError):
            self.error.setText('Не вдалося відтворити аудіо.')
            self.error.show()


    def select_tab(self, index):
        # A popup from the previous page must not float over the new page.
        for selector in self.findChildren(SideSelector):
            selector.menu.dismiss(animated=False)
        for order, card in self.section_cards.items():
            card.setVisible(order == index)
        self.root_layout.invalidate()

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
            self.audio_language_buttons.get(preferences.get('audio_language'), self.audio_language_buttons['ua']).setChecked(True)
            self.auto_updates.setChecked(preferences.get('check_updates', True))
            self.error.clear()
            self.error.hide()
        finally:
            self.loading = False

    def values(self):
        return {'region': self.region_selector.currentData(), 'group': self.queue_selector.currentText(), 'overlay_topmost': self.topmost.isChecked(),
                'refresh_minutes': self.interval.value(), 'notify_5_minutes': self.notify_5.isChecked(),
                'notify_10_minutes': self.notify_10.isChecked(), 'overlay_position': self.position.currentData(),
                'audio_language': self.selected_audio_language(), 'check_updates': self.auto_updates.isChecked()}

