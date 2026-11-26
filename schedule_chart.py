from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy
from core import clock_text


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
            title = ('Сьогодні' if offset == 0 else 'Завтра') + f' · {date:%d.%m}'
            rows.append((title, days.get(date.isoformat())))
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
            label.setStyleSheet('font-size: 12px; color: #a6b6cd;')
            layout.addWidget(label)
            segments = day_segments(day)
            if not segments:
                message = 'Екстрені відключення — графік не діє' if day and day['status'] == 'emergency' else 'Графік ще не опубліковано'
                label = QLabel(message)
                label.setWordWrap(True)
                label.setStyleSheet('background: #263142; color: #a6b6cd; padding: 7px; border-radius: 4px; font-size: 12px;')
                layout.addWidget(label)
            else:
                strip = QWidget()
                grid = QHBoxLayout(strip)
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setSpacing(4)
                for index, (start, end, state) in enumerate(segments):
                    text = f'{clock_text(start)} – {clock_text(end)}'
                    label = QLabel(f'{clock_text(start)}\n{clock_text(end)}')
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setMinimumHeight(36)
                    label.setMinimumWidth(54)
                    label.setToolTip(names[state] + ' · ' + text)
                    label.setAccessibleName(names[state] + ' · ' + text)
                    bg, fg = colors[state]
                    label.setStyleSheet(f'background: {bg}; color: {fg}; border-radius: 4px; font-size: 14px; font-weight: 600;')
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
