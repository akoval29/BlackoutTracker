import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from app import SettingsPanel, STYLE
from preferences import normalize_settings


class SideSelectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def test_both_menus_open_left_and_apply_selection(self):
        panel = SettingsPanel(normalize_settings({}))
        panel.resize(360, 560)
        panel.move(450, 0)
        panel.show()
        self.app.processEvents()
        saved = []
        panel.saved.connect(saved.append)
        try:
            for selector in (panel.region_choice, panel.combo, panel.position, panel.sound_choice):
                selector.showPopup()
                self.app.processEvents()
                self.assertTrue(selector.menu.isVisible())
                self.assertLess(selector.menu.geometry().right(), panel.mapToGlobal(QPoint()).x())
                selector.menu.actions()[2].trigger()
                self.assertEqual(selector.currentIndex(), 2)
                self.assertEqual(saved[-1], panel.values())
                selector.hidePopup()
                self.assertFalse(selector.menu.isVisible())
            count = len(saved)
            panel.position.showPopup()
            panel.position.hidePopup()
            self.assertEqual(len(saved), count)
        finally:
            panel.close()
            panel.deleteLater()
