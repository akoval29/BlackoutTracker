"""Queued, non-activating topmost event notifications."""
from collections import deque
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from blackout_tracker.event_journal import event_summary


class EventToast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName('eventToast')
        self.setStyleSheet('#eventToast { background: #2a384b; border: 1px solid #60758f; }')
        self.setFixedWidth(360)
        self.pending = deque()
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel('BlackoutTracker'))
        row.addStretch()
        close = QPushButton('×')
        close.setAccessibleName('Закрити повідомлення')
        close.clicked.connect(self.show_next)
        row.addWidget(close)
        layout.addLayout(row)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet('font-weight: 600; color: #f6ad55;')
        layout.addWidget(self.title)
        self.description = QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(6000)
        self.timer.timeout.connect(self.show_next)

    def enqueue(self, events):
        self.pending.extend(events)
        if not self.timer.isActive():
            self.show_next()

    def show_next(self):
        self.timer.stop()
        self.hide()
        if not self.pending:
            return
        event = self.pending.popleft()
        self.title.setText(event['title'])
        self.description.setText(event_summary(event))
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() + 1, area.bottom() - self.height() + 1)
        self.show()
        self.raise_()
        self.timer.start()

    def stop(self):
        self.pending.clear()
        self.timer.stop()
        self.hide()
