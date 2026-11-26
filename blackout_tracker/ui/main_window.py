import json
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QRect, QPoint, QEvent, QVariantAnimation, QEasingCurve
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSystemTrayIcon, QMenu, QFrame, QScrollArea, QSizePolicy, QLayout, QAbstractButton, QAbstractSlider, QAbstractSpinBox
from blackout_tracker.settings import load_settings
from blackout_tracker.notifications import AlertState
from blackout_tracker.ui.schedule_chart import ScheduleChart
from blackout_tracker.ui.side_selector import SideSelector
from blackout_tracker.ui.outside_click_monitor import OutsideClickMonitor
from blackout_tracker.regions import DEFAULT_REGION, REGIONS
from blackout_tracker.schedule import KYIV_TIMEZONE, get_schedule_state, is_schedule_fresh, parse_timestamp
from blackout_tracker.resources import load_app_icon
from blackout_tracker.storage import save_json_atomic
from blackout_tracker.ui.settings_panel import SettingsPanel
from blackout_tracker.audio import play_warning
from blackout_tracker.ui.countdown_widget import CountdownWidget
from blackout_tracker.schedule_worker import ScheduleFetchWorker


class MainWindow(QMainWindow):
    def __init__(self, folder, group):
        super().__init__()
        self.folder, self.group = folder, group
        self.preferences = load_settings(folder / 'settings.json', group)
        self.region = self.preferences['region']
        self.group = self.preferences['group']
        self.alerts = AlertState()
        self.overlay = CountdownWidget()
        self.overlay.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.preferences['overlay_topmost'])
        self.overlay.dismissed.connect(self.dismiss_overlay)
        self.widget_manually_enabled = False
        self.schedule = None
        self.schedule_worker = None
        self.offline = False
        self.quitting = False
        self.hiding_to_tray = False
        self.setWindowTitle('BlackoutTracker')
        self.setWindowIcon(load_app_icon())
        self.expanded = False
        self.settings_open = False
        self.drawer_width = 360
        self.panel_height = 240.0
        self.drawer_reveal = 0.0
        self.panel_animation = QVariantAnimation(self)
        self.panel_animation.setDuration(260)
        self.panel_animation.valueChanged.connect(self.animate_panels)
        self.panel_animation.finished.connect(self.finish_tray_animation)
        self.panel_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
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
        self.settings_panel.position_requested.connect(self.show_overlay)
        self.drawer_clip.hide()
        layout = QVBoxLayout(root)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        header = QHBoxLayout()
        header.setSpacing(4)
        logo = QLabel()
        logo.setFixedSize(24, 24)
        logo.setPixmap(load_app_icon().pixmap(24, 24))
        logo.setAccessibleName('Іконка BlackoutTracker')
        header.addWidget(logo)
        title = QLabel('BlackoutTracker')
        title.setStyleSheet('font-size: 16px; font-weight: 700;')
        header.addWidget(title)
        header.addStretch()
        self.widget_button = QPushButton('Віджет: викл')
        self.widget_button.setStyleSheet('font-size: 12px; padding: 9px 7px;')
        self.widget_button.clicked.connect(self.toggle_overlay)
        header.addWidget(self.widget_button)
        self.expand_button = QPushButton('Подробиці ↑')
        self.expand_button.setStyleSheet('font-size: 12px; padding: 9px 7px;')
        self.expand_button.clicked.connect(self.toggle_expanded)
        header.addWidget(self.expand_button)
        hide = QPushButton('×')
        hide.setAccessibleName('Сховати у трей')
        hide.setToolTip('Сховати у трей')
        hide.setFixedWidth(32)
        hide.setStyleSheet('padding: 9px 4px;')
        hide.clicked.connect(self.hide_to_tray)
        header.addWidget(hide)
        layout.addLayout(header)
        self.subtitle = QLabel()
        self.subtitle.setObjectName('muted')
        card = QFrame()
        card.setObjectName('card')
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        cardlayout = QVBoxLayout(card)
        cardlayout.setContentsMargins(12, 8, 12, 8)
        cardlayout.setSpacing(6)
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
        details_layout.setSpacing(12)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details.setWidget(details_body)
        self.chart = ScheduleChart()
        details_layout.addWidget(self.chart)
        self.update_status_label = QLabel()
        self.update_status_label.setWordWrap(True)
        self.update_status_label.setObjectName('muted')
        details_layout.addWidget(self.update_status_label)
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
        self.tray = QSystemTrayIcon(load_app_icon(), self)
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
        self.outside_clicks = OutsideClickMonitor(self)
        self.outside_clicks.pressed.connect(self.outside_pressed)
        QApplication.instance().installEventFilter(self)
        QTimer.singleShot(0, self.refresh)

    def screen_changed(self, screen):
        self.dock_screen = screen
        if screen:
            screen.availableGeometryChanged.connect(self.anchor)
            self.anchor()

    def anchor(self, *_, animate=False):
        if self.hiding_to_tray:
            return
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
        self.panel_animation.stop()
        self.setGeometry(QRect(area.right() - width + 1,
                               area.bottom() - height + 1, width, height))
        self.main_start_height = self.panel_height
        self.main_end_height = min(530 if self.expanded else 240, height)
        self.drawer_start = self.drawer_reveal
        self.drawer_end = self.drawer_width if self.settings_open else 0
        if animate and self.isVisible():
            self.panel_animation.setStartValue(0.0)
            self.panel_animation.setEndValue(1.0)
            self.panel_animation.start()
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
        if self.hiding_to_tray:
            return
        self.expanded = not self.expanded
        if not self.expanded:
            self.settings_open = False
        self.details.setVisible(self.expanded)
        self.expand_button.setText('Подробиці ↓' if self.expanded else 'Подробиці ↑')
        self.anchor(animate=True)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.expanded:
            self.panel_height = 0.0
            self.anchor(animate=True)
        else:
            self.anchor()
        if hasattr(self, 'outside_clicks'):
            self.outside_clicks.start()

    def hideEvent(self, event):
        if hasattr(self, 'outside_clicks'):
            self.outside_clicks.stop()
        super().hideEvent(event)

    def outside_pressed(self, point):
        if not self.isVisible():
            return
        widgets = [self.main_panel]
        if self.drawer_clip.isVisible():
            widgets.append(self.drawer_clip)
        widgets.extend(selector.menu for selector in self.settings_panel.findChildren(SideSelector)
                       if selector.menu.isVisible())
        if self.tray.contextMenu().isVisible():
            widgets.append(self.tray.contextMenu())
        for widget in widgets:
            if QRect(widget.mapToGlobal(QPoint()), widget.size()).contains(point):
                return
        self.hide_to_tray()

    def eventFilter(self, watched, event):
        if self.isVisible() and event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if isinstance(watched, QWidget) and (watched == self.main_panel or self.main_panel.isAncestorOf(watched)):
                control = watched
                while control != self.main_panel:
                    if isinstance(control, (QAbstractButton, QComboBox, QAbstractSlider, QAbstractSpinBox)):
                        return False
                    control = control.parentWidget()
                self.toggle_expanded()
                return True
        return super().eventFilter(watched, event)

    def load_cache(self):
        self.schedule = None
        try:
            path = self.folder / f'cache-{self.region}-{self.group}.json'
            if not path.exists() and self.region == DEFAULT_REGION:
                path = self.folder / f'cache-{self.group}.json'
            cached = json.loads(path.read_text(encoding='utf-8'))
            if cached['group'] == self.group and cached.get('region', DEFAULT_REGION) == self.region and cached.get('provider') == 'github':
                get_schedule_state(cached, datetime.now(KYIV_TIMEZONE))
                is_schedule_fresh(cached, datetime.now(KYIV_TIMEZONE))
                self.schedule = cached
                self.offline = True
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def refresh(self):
        if self.schedule_worker is not None:
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText('Оновлюємо…')
        self.schedule_worker = ScheduleFetchWorker(self.group, self.region)
        self.schedule_worker.ready.connect(self.received)
        self.schedule_worker.failed.connect(self.failed)
        self.schedule_worker.finished.connect(self.finished)
        self.schedule_worker.start()

    def received(self, schedule):
        if (schedule.get('region', DEFAULT_REGION), schedule['group']) != (self.region, self.group):
            return
        self.schedule, self.offline = schedule, False
        self.warning.setText(schedule.get('warning', ''))
        self.warning.setToolTip('')
        try:
            save_json_atomic(self.folder / f'cache-{self.region}-{self.group}.json', schedule)
        except OSError:
            self.warning.setText('Графік отримано, але не вдалося зберегти локальну копію.')
        self.tick()

    def failed(self, message):
        if self.schedule_worker is not None and (self.schedule_worker.region, self.schedule_worker.group) != (self.region, self.group):
            return
        self.offline = True
        self.warning.setText('Немає оновлення. Показано збережений графік.' if self.schedule else f"Джерела недоступні. Повторимо через {self.preferences['refresh_minutes']} хв.")
        self.warning.setToolTip(message)
        self.tick()

    def finished(self):
        old_selection = (self.schedule_worker.region, self.schedule_worker.group)
        self.schedule_worker.deleteLater()
        self.schedule_worker = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText('Оновити графік відключень')
        if self.quitting:
            QApplication.instance().quit()
        elif old_selection != (self.region, self.group):
            self.refresh()

    def tick(self):
        now = datetime.now(KYIV_TIMEZONE)
        label, target, color = get_schedule_state(self.schedule, now)
        stale = bool(self.schedule) and not is_schedule_fresh(self.schedule, now)
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
        self.tray.setToolTip(f'{REGIONS[self.region]} · Черга {self.group}\n{label}\n{self.countdown.text()}')
        self.chart.set_schedule(self.schedule, now)
        if self.schedule:
            checked = parse_timestamp(self.schedule['checked']).astimezone(KYIV_TIMEZONE)
            updated = self.schedule.get('updated')
            detail = f' · графік від {parse_timestamp(updated).astimezone(KYIV_TIMEZONE):%d.%m %H:%M}' if updated else ''
            self.update_status_label.setText(f"Перевірено {checked:%d.%m %H:%M}{detail}")
        else:
            self.update_status_label.setText(f"Перевірка графіка кожні {self.preferences['refresh_minutes']} хв")
        if not self.quitting:
            visible, sound = self.alerts.evaluate(self.schedule, now, self.group, self.widget_manually_enabled)
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
        self.widget_manually_enabled = False
        self.alerts.dismiss()
        self.sync_widget_button()

    def show_overlay(self):
        self.widget_manually_enabled = True
        self.alerts.dismissed = None
        self.tick()

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.dismiss_overlay()
        else:
            self.widget_manually_enabled = True
            self.alerts.dismissed = None
            self.tick()

    def configure(self):
        if self.hiding_to_tray:
            return
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
            save_json_atomic(self.folder / 'settings.json', updated)
        except OSError as exc:
            self.settings_panel.error.setText(f'Не вдалося зберегти: {exc}')
            self.settings_panel.error.show()
            return
        if updated['overlay_position'] != self.preferences['overlay_position']:
            self.widget_manually_enabled = True
            self.alerts.dismissed = None
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
        if self.hiding_to_tray:
            self.panel_animation.stop()
            self.hiding_to_tray = False
            self.anchor(animate=True)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.reveal()

    def hide_to_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable() or not self.isVisible() or self.hiding_to_tray:
            return
        for selector in self.settings_panel.findChildren(SideSelector):
            selector.menu.dismiss(animated=False)
        self.panel_animation.stop()
        self.hiding_to_tray = True
        self.main_start_height = self.panel_height
        self.main_end_height = 0.0
        self.drawer_start = self.drawer_reveal
        self.drawer_end = self.drawer_reveal
        self.panel_animation.setStartValue(0.0)
        self.panel_animation.setEndValue(1.0)
        self.panel_animation.start()

    def finish_tray_animation(self):
        if not self.hiding_to_tray:
            return
        self.hide()
        self.hiding_to_tray = False
        self.settings_open = False
        self.expanded = False
        self.details.hide()
        self.expand_button.setText('Подробиці ↑')
        self.drawer_reveal = 0.0
        self.arrange_panels()

    def closeEvent(self, event):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide_to_tray()
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
        if self.schedule_worker is None:
            QApplication.instance().quit()

