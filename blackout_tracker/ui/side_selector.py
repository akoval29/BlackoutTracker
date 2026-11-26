import math
from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QWidget, QScrollArea,
    QGridLayout, QPushButton, QStylePainter, QStyleOptionComboBox, QStyle)


def direction_icon(position):
    dx, dy = {'top-left': (-1, -1), 'top': (0, -1), 'top-right': (1, -1),
              'bottom-left': (-1, 1), 'bottom': (0, 1), 'bottom-right': (1, 1)}[position]
    length = math.hypot(dx, dy)
    dx, dy = dx / length, dy / length
    image = QPixmap(16, 16)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#e9eff9'), 1.5))
    tip = QPointF(8 + dx * 6, 8 + dy * 6)
    painter.drawLine(QPointF(8 - dx * 5, 8 - dy * 5), tip)
    for side in (-1, 1):
        painter.drawLine(tip, QPointF(tip.x() - dx * 4 + side * dy * 3,
                                     tip.y() - dy * 4 - side * dx * 3))
    painter.end()
    return QIcon(image)


class SelectorPopup(QFrame):
    def __init__(self, selector):
        super().__init__(selector, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.selector = selector
        self.setObjectName('choiceMenu')
        self.setStyleSheet('#choiceMenu { background: #182536; border: 1px solid #3b4e67; }')
        self.scroll = QScrollArea(self)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.buttons = []
        self.target = QRect()
        self.closing = False
        self.panel_animation = QPropertyAnimation(self, b'geometry', self)
        self.panel_animation.setDuration(260)
        self.panel_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.panel_animation.finished.connect(self.finished)

    def open_choices(self):
        selector = self.selector
        panel = selector.panel
        main = getattr(panel.window(), 'main_panel', panel)
        main_top = main.mapToGlobal(QPoint()).y()
        area = selector.screen().availableGeometry()
        height_limit = max(1, min(main.height(), area.height()))
        row_height = 36
        rows = max(1, (height_limit - 24) // row_height)
        columns = max(1, math.ceil(selector.count() / rows))
        cell_width = max(76, max((selector.fontMetrics().horizontalAdvance(selector.itemText(i))
                                  for i in range(selector.count())), default=80) + (48 if getattr(selector, "menu_columns", None) else 28))
        edge = panel.mapToGlobal(QPoint()).x() - 4
        available_width = max(1, edge - area.left())
        columns = min(columns, max(1, available_width // cell_width))
        if getattr(selector, 'menu_columns', None):
            columns = selector.menu_columns
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(4)
        self.buttons = []
        for index in range(selector.count()):
            button = QPushButton(selector.itemText(index))
            if getattr(selector, 'menu_columns', None):
                button.setIcon(direction_icon(selector.itemData(index)))
            button.setCheckable(True)
            button.setChecked(index == selector.currentIndex())
            button.setFixedHeight(32)
            button.setStyleSheet('QPushButton { padding: 4px 8px; font-size: 12px; }'
                                'QPushButton:checked { background: #376254; border-color: #5ee0af; }')
            button.clicked.connect(lambda checked=False, i=index: self.choose(i))
            grid.addWidget(button, index // columns, index % columns)
            self.buttons.append(button)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(body)
        height = min(height_limit, math.ceil(selector.count() / columns) * row_height + 24)
        width = min(area.width(), columns * cell_width + 12)
        # On narrow screens the menu stays usable through scrolling.
        width = min(width, available_width) if available_width >= 76 else min(width, area.width())
        x = max(area.left(), edge - width)
        y = selector.mapToGlobal(QPoint()).y()
        y = max(area.top(), main_top, min(y, main_top + main.height() - height, area.bottom() - height + 1))
        self.target = QRect(x, y, width, height)
        self.panel_animation.stop()
        self.closing = False
        self.setGeometry(QRect(x + width - 1, y, 1, height))
        self.show()
        self.panel_animation.setStartValue(self.geometry())
        self.panel_animation.setEndValue(self.target)
        self.panel_animation.start()

    def choose(self, index):
        self.selector.setCurrentIndex(index)
        self.selector.activated.emit(index)
        self.dismiss()

    def dismiss(self, animated=True):
        if not self.isVisible():
            return
        self.panel_animation.stop()
        self.closing = True
        if not animated:
            self.hide()
            return
        end = QRect(self.target.right(), self.target.y(), 1, self.target.height())
        self.panel_animation.setStartValue(self.geometry())
        self.panel_animation.setEndValue(end)
        self.panel_animation.start()

    def finished(self):
        if self.closing:
            self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'scroll'):
            self.scroll.setGeometry(0, 0, max(1, self.target.width()), self.height())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(event)


class SideSelector(QComboBox):
    """Labelled selector with an animated, height-limited choice grid."""

    def __init__(self, label, panel):
        super().__init__(panel)
        self.label = label
        self.panel = panel
        self.menu = SelectorPopup(self)
        self.setAccessibleName(label)
        self.setStyleSheet('QComboBox { font-size: 12px; padding: 9px 7px; }')
        QApplication.instance().installEventFilter(self)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = f'{self.label}: {self.currentText()}'
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.showPopup()
            event.accept()
        else:
            super().mousePressEvent(event)

    def showPopup(self):
        if self.menu.isVisible() and not self.menu.closing:
            self.menu.dismiss()
        else:
            self.menu.open_choices()

    def hidePopup(self):
        self.menu.dismiss()
        super().hidePopup()

    def eventFilter(self, watched, event):
        if self.menu.isVisible():
            if event.type() == QEvent.Type.MouseButtonPress:
                point = event.globalPosition().toPoint()
                own_rect = QRect(self.mapToGlobal(QPoint()), self.size())
                if not self.menu.geometry().contains(point) and not own_rect.contains(point):
                    self.menu.dismiss()
            elif event.type() in (QEvent.Type.Hide, QEvent.Type.Move, QEvent.Type.Resize):
                if watched in (self.panel, self.panel.window(), getattr(self.panel.window(), 'main_panel', None)):
                    self.menu.dismiss(animated=False)
        return super().eventFilter(watched, event)
