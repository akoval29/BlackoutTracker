from datetime import timedelta

from PySide6.QtCore import Qt, QTimer, QElapsedTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient
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
        self.background = QColor(background)
        self.foreground = QColor(foreground)
        self.elapsed_fraction = 0.0
        self.wave_center = 0.0
        self.wave_radius = 1.0
        self.setAccessibleName(description)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(36)
        self.setMinimumWidth(54)
        hover_background = QColor(background).lighter(125).name()
        self.setStyleSheet(
            f'QLabel {{ background: {background}; color: {foreground}; border: 1px solid transparent; '
            'border-radius: 4px; font-size: 14px; font-weight: 600; }'
            f'QLabel:hover {{ background: {hover_background}; border-color: {foreground}; }}')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()), 4, 4)
        painter.fillPath(shape, self.background.lighter(125) if self.underMouse() else self.background)
        if self.elapsed_fraction > 0:
            painter.save()
            painter.setClipPath(shape)
            painter.setClipRect(QRectF(0, 0, self.width() * self.elapsed_fraction, self.height()),
                                Qt.ClipOperation.IntersectClip)
            # Every block samples the same travelling band in strip coordinates.
            # Clipping to the elapsed portion leaves future time and gaps untouched.
            center = self.wave_center - self.x()
            gradient = QLinearGradient(center - self.wave_radius, 0,
                                       center + self.wave_radius, 0)
            for position, alpha in ((0, 0), (0.25, 18), (0.5, 72), (0.75, 18), (1, 0)):
                tint = QColor(self.foreground)
                tint.setAlpha(alpha)
                gradient.setColorAt(position, tint)
            painter.fillRect(self.rect(), gradient)
            painter.restore()
        if self.underMouse():
            painter.setPen(self.foreground)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        painter.setPen(self.foreground)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

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
        self.today_blocks = []
        self.day_titles = []
        self.elapsed_minutes = 0.0
        self.wave_clock = QElapsedTimer()
        self.wave_clock.start()
        self.wave_timer = QTimer(self)
        self.wave_timer.setInterval(33)
        self.wave_timer.timeout.connect(self.animate_wave)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(12)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setAccessibleName('Інтервали світла та відключень')

    def showEvent(self, event):
        super().showEvent(event)
        if self.today_blocks:
            self.wave_timer.start()
        self.animate_wave()

    def hideEvent(self, event):
        self.wave_timer.stop()
        super().hideEvent(event)

    def animate_wave(self):
        endpoint = 0.0
        for block, start, end in self.today_blocks:
            block.elapsed_fraction = max(0.0, min(1.0, (self.elapsed_minutes - start) / (end - start)))
            if block.elapsed_fraction > 0:
                endpoint = block.x() + block.width() * block.elapsed_fraction
        radius = max(24.0, endpoint * 0.18)
        phase = (self.wave_clock.elapsed() % 1280) / 1280
        center = -radius + phase * (endpoint + 2 * radius)
        for block, _, _ in self.today_blocks:
            block.wave_center = center
            block.wave_radius = radius
            block.update()

    def set_schedule(self, schedule, now):
        self.elapsed_minutes = now.hour * 60 + now.minute + now.second / 60
        days = {d['date']: d for d in (schedule or {}).get('days', [])}
        rows = []
        for offset in range(2):
            date = now.date() + timedelta(days=offset)
            day = days.get(date.isoformat())
            if offset == 1 and (not day or day['status'] == 'unknown'):
                continue
            title = ('Сьогодні' if offset == 0 else 'Завтра') + f' · {date:%d.%m.%y}'
            rows.append((title, day))
        if rows == self.rows:
            self.day_titles[0].setText(f'{rows[0][0]} {now:%H:%M}')
            self.animate_wave()
            return
        self.rows = rows
        self.today_blocks = []
        self.day_titles = []
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        colors = {'on': ('#254b3e', '#b0f0d1'), 'off': ('#713b42', '#ffe1e3'),
                  'maybe': ('#61502d', '#ffdfa1')}
        names = {'on': 'Є світло за графіком', 'off': 'Відключення', 'maybe': 'Можливе відключення'}
        for row_index, (title, day) in enumerate(rows):
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(7)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            label = QLabel(f'{title} {now:%H:%M}' if row_index == 0 else title)
            self.day_titles.append(label)
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
                    if row_index == 0:
                        self.today_blocks.append((label, start, end))
                scroll = QScrollArea()
                scroll.setFrameShape(QScrollArea.Shape.NoFrame)
                scroll.setWidgetResizable(True)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll.setWidget(strip)
                scroll.setFixedHeight(52)
                layout.addWidget(scroll)
            self.body.addWidget(section)
        if self.isVisible() and self.today_blocks:
            self.wave_timer.start()
        else:
            self.wave_timer.stop()
        self.animate_wave()
