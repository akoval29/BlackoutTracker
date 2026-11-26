from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QComboBox, QMenu, QStylePainter, QStyleOptionComboBox, QStyle


class SideSelect(QComboBox):
    """A labelled selector with a separate menu beside the settings panel."""

    def __init__(self, label, panel):
        super().__init__(panel)
        self.label = label
        self.panel = panel
        self.menu = QMenu(self)
        self.menu.setStyleSheet('QMenu { menu-scrollable: 1; }')
        self.setAccessibleName(label)
        self.setStyleSheet('font-size: 12px; padding: 9px 7px;')

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = f'{self.label}: {self.currentText()}'
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)

    def showPopup(self):
        self.menu.clear()
        for index in range(self.count()):
            action = self.menu.addAction(self.itemText(index))
            action.setCheckable(True)
            action.setChecked(index == self.currentIndex())
            action.triggered.connect(lambda checked=False, i=index: self.setCurrentIndex(i))
        self.menu.ensurePolished()
        size = self.menu.sizeHint()
        panel_left = self.panel.mapToGlobal(QPoint(0, 0)).x()
        y = self.mapToGlobal(QPoint(0, 0)).y()
        x = panel_left - size.width() - 4
        screen = self.screen()
        if screen:
            area = screen.availableGeometry()
            x = max(area.left(), x)
            y = max(area.top(), min(y, area.bottom() - size.height() + 1))
        self.menu.popup(QPoint(x, y))
        if self.currentIndex() >= 0:
            self.menu.setActiveAction(self.menu.actions()[self.currentIndex()])

    def hidePopup(self):
        self.menu.close()
        super().hidePopup()
