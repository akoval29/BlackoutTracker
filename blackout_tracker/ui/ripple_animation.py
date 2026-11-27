from PySide6.QtCore import Qt, QVariantAnimation, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RippleAnimation(QWidget):
    """Short, click-through waves centred on the timer; never takes focus."""

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet('background: transparent;')
        self.setFixedSize(320, 320)
        self.progress = 0.0
        self.repeating = False
        self.color = QColor('#5ee0af')
        self.panel_animation = QVariantAnimation(self)
        self.panel_animation.setDuration(1100)
        self.panel_animation.setStartValue(0.0)
        self.panel_animation.setEndValue(1.0)
        self.panel_animation.valueChanged.connect(self.advance)
        self.panel_animation.finished.connect(self.hide)

    def start(self, center, color, topmost, repeat=False):
        self.panel_animation.stop()
        self.repeating = repeat
        self.panel_animation.setLoopCount(-1 if repeat else 1)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
        self.move(center.x() - 160, center.y() - 160)
        self.color = QColor(color)
        self.progress = 0.0
        self.show()
        self.panel_animation.start()

    def advance(self, value):
        self.progress = value
        self.update()

    def stop(self):
        self.panel_animation.stop()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for delay in (0.0, 0.16, 0.32):
            phase = ((self.progress - delay) % 1.0 if self.repeating
                     else (self.progress - delay) / (1.0 - delay))
            if not 0 <= phase < 1:
                continue
            radius = 7 + 148 * phase
            color = QColor(self.color)
            color.setAlphaF(0.65 * (1 - phase) ** 1.5)
            painter.setPen(QPen(color, 1.6))
            painter.drawEllipse(QPointF(160, 160), radius, radius)
        painter.end()
