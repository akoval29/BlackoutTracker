import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blackout_tracker.ui.main_window import MainWindow
from blackout_tracker.settings import load_settings


class WindowInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_clicks_outside_click_and_reappearance(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(MainWindow, 'refresh'), patch('blackout_tracker.ui.main_window.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
            window = MainWindow(Path(directory), '6.1')
            try:
                window.show()
                window.outside_clicks.stop()
                self.assertLess(window.panel_height, max(window.main_start_height, window.main_end_height))
                window.panel_animation.setCurrentTime(130)
                self.assertGreater(window.panel_height, 0)
                self.assertLess(window.panel_height, max(window.main_start_height, window.main_end_height))
                window.panel_animation.setCurrentTime(260)
                QTest.mouseClick(window.countdown, Qt.MouseButton.LeftButton)
                self.assertTrue(window.expanded)
                window.panel_animation.setCurrentTime(260)
                self.assertEqual(window.expand_button.text(), 'Згорнути ↑')
                for widget in (window.chart, window.update_status_label, window.main_panel):
                    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
                    self.assertTrue(window.expanded)
                QTest.mouseClick(window.expand_button, Qt.MouseButton.LeftButton)
                self.assertFalse(window.expanded)
                window.panel_animation.setCurrentTime(260)
                self.assertEqual(window.expand_button.text(), 'Показати графік ↓')
                QTest.mouseClick(window.expand_button, Qt.MouseButton.LeftButton)
                self.assertTrue(window.expanded)
                window.panel_animation.setCurrentTime(260)
                QTest.mouseClick(window.subtitle, Qt.MouseButton.LeftButton)
                self.assertFalse(window.expanded)
                expanded_height = window.details.height()
                self.assertTrue(window.details.isVisible())
                window.panel_animation.setCurrentTime(130)
                self.app.processEvents()
                self.assertTrue(window.details.isVisible())
                self.assertLess(window.details.height(), expanded_height)
                collapsed_target = window.main_end_height
                window.update_content_height()
                self.assertEqual(window.main_end_height, collapsed_target)
                # Reverse midway: content must remain visible without a flash.
                window.toggle_expanded()
                self.assertTrue(window.details.isVisible())
                window.panel_animation.setCurrentTime(260)
                window.toggle_expanded()
                window.panel_animation.setCurrentTime(259)
                self.app.processEvents()
                self.assertTrue(window.details.isVisible())
                self.assertLessEqual(window.details.height(), 1)
                window.panel_animation.setCurrentTime(260)
                self.assertTrue(window.details.isHidden())
                self.assertTrue(window.overlay.isVisible())
                self.assertEqual(window.preferences['overlay_position'], 'bottom')
                window.widget_button.click()
                self.assertFalse(window.overlay.isVisible())
                self.assertFalse(load_settings(Path(directory) / 'settings.json', '6.1')['overlay_enabled'])
                window.widget_button.click()
                self.assertTrue(load_settings(Path(directory) / 'settings.json', '6.1')['overlay_enabled'])
                self.assertFalse(window.expanded)
                self.assertTrue(window.overlay.isVisible())
                window.overlay.hide()
                window.dismiss_overlay()
                window.settings_panel.position.setCurrentIndex(0)
                self.assertTrue(window.overlay.isVisible())
                self.assertEqual(load_settings(Path(directory) / 'settings.json', '6.1')['overlay_position'], window.settings_panel.position.currentData())
                window.overlay.hide()
                window.dismiss_overlay()
                window.settings_panel.position.activated.emit(0)
                self.assertTrue(window.overlay.isVisible())
                window.configure()
                window.panel_animation.setCurrentTime(260)
                window.outside_pressed(window.settings_panel.mapToGlobal(QPoint(20, 20)))
                self.assertTrue(window.isVisible())
                window.outside_pressed(QPoint(-10000, -10000))
                self.assertTrue(window.isVisible())
                window.panel_animation.setCurrentTime(130)
                self.assertGreater(window.panel_height, 0)
                self.assertLess(window.panel_height, max(window.main_start_height, window.main_end_height))
                window.panel_animation.setCurrentTime(260)
                self.assertFalse(window.isVisible())
                self.assertFalse(window.settings_open)
                self.assertFalse(window.expanded)
                window.reveal()
                window.outside_clicks.stop()
                self.assertTrue(window.isVisible())
                self.assertLess(window.panel_height, max(window.main_start_height, window.main_end_height))
                window.panel_animation.setCurrentTime(260)
                self.assertEqual(window.main_panel.height(), window.main_end_height)
                window.toggle_expanded()
                window.panel_animation.setCurrentTime(260)
                window.close()
                self.assertTrue(window.hiding_to_tray)
                window.panel_animation.setCurrentTime(130)
                height = window.panel_height
                window.hide_to_tray()
                self.assertEqual(window.panel_height, height)
                window.reveal()
                self.assertFalse(window.hiding_to_tray)
                window.panel_animation.setCurrentTime(260)
                self.assertTrue(window.isVisible())
                self.assertEqual(window.main_panel.height(), window.main_end_height)
                window.close()
                window.panel_animation.setCurrentTime(260)
                self.assertFalse(window.isVisible())
            finally:
                window.hide()
                window.overlay.hide()
                window.tray.hide()
                window.deleteLater()
