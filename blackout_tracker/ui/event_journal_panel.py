"""Readable event cards in an independently scrollable side panel."""
from copy import deepcopy
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea
from blackout_tracker.event_journal import describe_day
from blackout_tracker.regions import REGIONS
from blackout_tracker.schedule import KYIV_TIMEZONE
from blackout_tracker.ui.theme import GRADIENT_DIVIDER_STYLE, JOURNAL_SCROLLBAR_STYLE


def text_label(text, style):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setStyleSheet(style)
    return label


class EventJournalPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.rendered_events = None
        self.scroll_revision = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        title = QLabel('Журнал подій')
        title.setStyleSheet('font-size: 20px; font-weight: 600;')
        layout.addWidget(title)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(GRADIENT_DIVIDER_STYLE)
        layout.addWidget(line)
        self.caption = QLabel()
        self.caption.setStyleSheet('color: #c0ccdc; font-size: 12px;')
        layout.addWidget(self.caption)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #f6ad55; font-size: 12px;')
        layout.addWidget(self.error)
        self.history = QScrollArea()
        self.history.setWidgetResizable(True)
        self.history.setFrameShape(QFrame.Shape.NoFrame)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.history.setStyleSheet('QScrollArea { background: transparent; border: none; }' + JOURNAL_SCROLLBAR_STYLE)
        self.history.verticalScrollBar().setSingleStep(32)
        self.history.setAccessibleName('Історія подій. Найновіші записи зверху')
        self.body = QWidget()
        self.body.setStyleSheet('background: transparent;')
        self.cards = QVBoxLayout(self.body)
        self.cards.setContentsMargins(0, 0, 8, 0)
        self.cards.setSpacing(10)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history.setWidget(self.body)
        layout.addWidget(self.history, 1)

    def refresh(self, journal):
        self.error.setText(journal.error)
        self.error.setVisible(bool(journal.error))
        if self.rendered_events == journal.events:
            return
        scrollbar = self.history.verticalScrollBar()
        old_value, old_maximum = scrollbar.value(), scrollbar.maximum()
        self.rendered_events = deepcopy(journal.events)
        self.caption.setText(f'Подій: {len(journal.events)} · Найновіші зверху')
        while self.cards.count():
            widget = self.cards.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        if not journal.events:
            self.cards.addWidget(text_label('Подій ще немає. Тут з’являться зміни графіка та екстрені відключення.',
                                           'color: #c0ccdc; font-size: 13px; padding: 10px 0px;'))
        for event in reversed(journal.events):
            self.cards.addWidget(self.event_card(event))
        self.scroll_revision += 1
        revision = self.scroll_revision
        def restore_position():
            if revision == self.scroll_revision:
                scrollbar.setValue(0 if old_value == 0 else old_value + max(0, scrollbar.maximum() - old_maximum))
        QTimer.singleShot(0, restore_position)

    def event_card(self, event):
        card = QFrame()
        card.setObjectName('eventCard')
        card.setStyleSheet('#eventCard { background: #34465e; border: 1px solid #526985; border-radius: 9px; }')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 11, 12, 12)
        layout.setSpacing(8)
        timestamp = datetime.fromisoformat(event['time']).astimezone(KYIV_TIMEZONE)
        row = QHBoxLayout()
        for value in (timestamp.strftime('%d.%m.%Y'), timestamp.strftime('%H:%M:%S')):
            row.addWidget(text_label(value, 'color: #c0ccdc; font-size: 12px;'))
        row.itemAt(1).widget().setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)
        color = '#ffbd78' if event['after']['status'] == 'emergency' else '#86e9cf'
        layout.addWidget(text_label(event['title'], f'color: {color}; font-size: 15px; font-weight: 600;'))
        region = REGIONS.get(event['region'], event['region'])
        date = datetime.fromisoformat(event['date']).strftime('%d.%m.%Y')
        layout.addWidget(text_label(f"{region} · Черга {event['group']}\nГрафік на {date}",
                                   'color: #d5dfed; font-size: 12px;'))
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(GRADIENT_DIVIDER_STYLE)
        layout.addWidget(line)
        comparison = QHBoxLayout()
        comparison.setSpacing(12)
        for title, day, color in [('Було', event['before'], '#c0ccdc'), ('Стало', event['after'], '#f2f6fc')]:
            column = QVBoxLayout()
            column.setSpacing(6)
            column.setAlignment(Qt.AlignmentFlag.AlignTop)
            column.addWidget(text_label(title, 'color: #9fb5d0; font-size: 12px; font-weight: 600;'))
            column.addWidget(text_label(describe_day(day).replace('; ', '\n'), f'color: {color}; font-size: 13px;'))
            comparison.addLayout(column, 1)
        layout.addLayout(comparison)
        return card
