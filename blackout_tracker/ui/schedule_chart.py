from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy
from blackout_tracker.schedule import format_time


def day_segments(day):
    """Cover the entire known day, merging adjacent equal states."""
    if not day or day['status'] in ('unknown', 'emergency'):
        return []
    boundaries = sorted({0, 1440, *(point for start, end, _ in day['intervals'] for point in (start, end))})
    result = []
    for start, end in zip(boundaries, boundaries[1:]):
        state = next((kind for a, b, kind in day['intervals'] if a <= start < b), 'on')
        if result and result[-1][2] == state:
            result[-1][1] = end
        else:
            result.append([start, end, state])
    return result


class ScheduleIntervalBlock(QLabel):
    """Highlight an interval and show its description in the day header."""

    def __init__(self, text, description, hint_label, background, foreground):
        super().__init__(text)
        self.description = description
        self.hint_label = hint_label
        self.setAccessibleName(description)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(36)
        self.setMinimumWidth(54)
        hover_background = QColor(background).lighter(125).name()
        self.setStyleSheet(
            f'QLabel {{ background: {background}; color: {foreground}; border: 1px solid transparent; '
            'border-radius: 4px; font-size: 14px; font-weight: 600; }'
            f'QLabel:hover {{ background: {hover_background}; border-color: {foreground}; }}')

    def enterEvent(self, event):
        self.hint_label.setText(self.description)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.hint_label.text() == self.description:
            self.hint_label.clear()
        super().leaveEvent(event)


class ScheduleChart(QWidget):
    """Equal-size interval cards in chronological reading order."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = None
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(12)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setAccessibleName('Інтервали світла та відключень')

    def set_schedule(self, schedule, now):
        days = {d['date']: d for d in (schedule or {}).get('days', [])}
        rows = []
        for offset in range(2):
            date = now.date() + timedelta(days=offset)
            day = days.get(date.isoformat())
            if offset == 1 and (not day or day['status'] == 'unknown'):
                continue
            title = ('Сьогодні' if offset == 0 else 'Завтра') + f' · {date:%d.%m}'
            rows.append((title, day))
        if rows == self.rows:
            return
        self.rows = rows
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        colors = {'on': ('#254b3e', '#b0f0d1'), 'off': ('#713b42', '#ffe1e3'),
                  'maybe': ('#61502d', '#ffdfa1')}
        names = {'on': 'Є світло за графіком', 'off': 'Відключення', 'maybe': 'Можливе відключення'}
        for title, day in rows:
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(7)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            label = QLabel(title)
            label.setStyleSheet('font-size: 12px; color: #c0ccdc;')
            header = QHBoxLayout()
            header.setSpacing(6)
            header.addWidget(label)
            hint = QLabel()
            hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            hint.setStyleSheet('font-size: 12px; color: #c0ccdc;')
            hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            header.addWidget(hint, 1)
            layout.addLayout(header)
            segments = day_segments(day)
            if not segments:
                message = 'Екстрені відключення — графік не діє' if day and day['status'] == 'emergency' else 'Графік ще не опубліковано'
                label = QLabel(message)
                label.setWordWrap(True)
                label.setStyleSheet('background: #263142; color: #c0ccdc; padding: 7px; border-radius: 4px; font-size: 12px;')
                layout.addWidget(label)
            else:
                strip = QWidget()
                grid = QHBoxLayout(strip)
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setSpacing(4)
                for index, (start, end, state) in enumerate(segments):
                    text = f'{format_time(start)} – {format_time(end)}'
                    bg, fg = colors[state]
                    label = ScheduleIntervalBlock(
                        f'{format_time(start)}\n{format_time(end)}',
                        names[state] + ' · ' + text, hint, bg, fg)
                    grid.addWidget(label, 1)
                scroll = QScrollArea()
                scroll.setFrameShape(QScrollArea.Shape.NoFrame)
                scroll.setWidgetResizable(True)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll.setWidget(strip)
                scroll.setFixedHeight(52)
                layout.addWidget(scroll)
            self.body.addWidget(section)
