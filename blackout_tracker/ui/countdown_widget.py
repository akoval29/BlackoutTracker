from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from blackout_tracker.ui.ripple_animation import RippleAnimation


class AnimatedTimerLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.scale = 1.0
        self.ink = QColor('#5ee0af')

    def paintEvent(self, event):
        if self.scale <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(self.ink)
        painter.setFont(self.font())
        center = self.rect().center()
        painter.translate(center)
        painter.scale(self.scale, self.scale)
        painter.translate(-center)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()



class CountdownWidget(QWidget):
    dismissed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('BlackoutTracker · Оверлей')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(90, 23)
        self.setStyleSheet('CountdownOverlay { background: transparent; border: none; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        self.timer = AnimatedTimerLabel('—')
        self.timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.timer)
        self.ripple = RippleAnimation(self)
        self.last_position = None
        self.position_animation = QPropertyAnimation(self, b'pos', self)
        self.position_animation.setDuration(500)
        self.position_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.text_animation = QVariantAnimation(self)
        self.text_animation.setDuration(420)
        self.text_animation.setStartValue(0.0)
        self.text_animation.setEndValue(1.0)
        self.text_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.text_animation.valueChanged.connect(self.animate_text)

    def animate_text(self, scale):
        self.timer.scale = scale
        self.timer.update()

    def present(self, label, countdown, color, position='top-right'):
        appearing = not self.isVisible()
        relocating = position != self.last_position
        self.last_position = position
        self.timer.setText(countdown)
        self.timer.ink = QColor(color)
        self.timer.setStyleSheet(f'font-size: 15px; font-weight: 650; color: {color};')
        self.timer.ensurePolished()
        metrics = self.timer.fontMetrics()
        # Reserve equal digit widths so ticking cannot move or resize the timer.
        digit_width = max(metrics.horizontalAdvance(str(digit)) for digit in range(10))
        width = digit_width * max(6, len(countdown.replace(':', ''))) + metrics.horizontalAdvance('::')
        self.setFixedSize(width + 2, metrics.height() + 2)
        self.setAccessibleName(f'{label}: {countdown}')
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            right = area.right() - self.width() + 1
            bottom = area.bottom() - self.height() + 1
            # Reserve the title-bar controls at the top-right of maximized windows.
            positions = {
                'top': (area.left() + (area.width() - self.width()) // 2, area.top()),
                'top-right': (max(area.left(), right - 150), area.top()),
                'top-left': (area.left(), area.top()),
                'bottom': (area.left() + (area.width() - self.width()) // 2, bottom),
                'bottom-right': (right, bottom),
                'bottom-left': (area.left(), bottom),
            }
            destination = QPoint(*positions.get(position, positions['top-right']))
            if appearing:
                self.position_animation.stop()
                self.move(destination)
            elif relocating:
                self.position_animation.stop()
                self.ripple.stop()
                self.text_animation.stop()
                self.animate_text(1.0)
                self.position_animation.setStartValue(self.pos())
                self.position_animation.setEndValue(destination)
                self.position_animation.start()
            elif self.position_animation.state() != self.position_animation.State.Running:
                self.move(destination)
        if not self.isVisible():
            self.show()
        if appearing:
            self.text_animation.stop()
            self.animate_text(0.0)
            self.text_animation.start()
            self.ripple.start(self.geometry().center(), color,
                              bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))

    def hideEvent(self, event):
        self.ripple.stop()
        self.position_animation.stop()
        self.text_animation.stop()
        super().hideEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.hide()
            self.dismissed.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

