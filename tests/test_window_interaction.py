import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app import Window


class WindowInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_clicks_outside_click_and_reappearance(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Window, 'refresh'), patch('app.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
            window = Window(Path(directory), '6.1')
            try:
                window.show()
                window.outside_clicks.stop()
                self.assertLess(window.panel_height, 240)
                window.motion.setCurrentTime(130)
                self.assertGreater(window.panel_height, 0)
                self.assertLess(window.panel_height, 240)
                window.motion.setCurrentTime(260)
                QTest.mouseClick(window.countdown, Qt.MouseButton.LeftButton)
                self.assertTrue(window.expanded)
                window.motion.setCurrentTime(260)
                QTest.mouseClick(window.subtitle, Qt.MouseButton.LeftButton)
                self.assertFalse(window.expanded)
                window.motion.setCurrentTime(260)
                window.widget_button.click()
                self.assertFalse(window.expanded)
                self.assertTrue(window.overlay.isVisible())
                window.overlay.hide()
                window.dismiss_overlay()
                window.settings_panel.position.setCurrentIndex(0)
                self.assertTrue(window.overlay.isVisible())
                window.overlay.hide()
                window.dismiss_overlay()
                window.settings_panel.position.activated.emit(0)
                self.assertTrue(window.overlay.isVisible())
                window.configure()
                window.motion.setCurrentTime(260)
                window.outside_pressed(window.settings_panel.mapToGlobal(QPoint(20, 20)))
                self.assertTrue(window.isVisible())
                window.outside_pressed(QPoint(-10000, -10000))
                self.assertTrue(window.isVisible())
                window.motion.setCurrentTime(130)
                self.assertGreater(window.panel_height, 0)
                self.assertLess(window.panel_height, 240)
                window.motion.setCurrentTime(260)
                self.assertFalse(window.isVisible())
                self.assertFalse(window.settings_open)
                self.assertFalse(window.expanded)
                window.reveal()
                window.outside_clicks.stop()
                self.assertTrue(window.isVisible())
                self.assertLess(window.panel_height, 240)
                window.motion.setCurrentTime(260)
                self.assertEqual(window.main_panel.height(), 240)
                window.toggle_expanded()
                window.motion.setCurrentTime(260)
                window.close()
                self.assertTrue(window.hiding_to_tray)
                window.motion.setCurrentTime(130)
                height = window.panel_height
                window.hide_to_tray()
                self.assertEqual(window.panel_height, height)
                window.reveal()
                self.assertFalse(window.hiding_to_tray)
                window.motion.setCurrentTime(260)
                self.assertTrue(window.isVisible())
                self.assertEqual(window.main_panel.height(), 530)
                window.close()
                window.motion.setCurrentTime(260)
                self.assertFalse(window.isVisible())
            finally:
                window.hide()
                window.overlay.hide()
                window.tray.hide()
                window.deleteLater()
