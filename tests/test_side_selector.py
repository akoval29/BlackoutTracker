import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blackout_tracker.ui.settings_panel import SettingsPanel
from blackout_tracker.ui.theme import APP_STYLESHEET
from blackout_tracker.settings import normalize_settings


class SideSelectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLESHEET)

    def test_both_menus_open_left_and_apply_selection(self):
        panel = SettingsPanel(normalize_settings({}))
        panel.resize(360, 560)
        panel.move(450, 0)
        panel.show()
        self.app.processEvents()
        saved = []
        panel.saved.connect(saved.append)
        try:
            for selector in (panel.region_selector, panel.queue_selector, panel.position):
                selector.showPopup()
                QTest.qWait(400)
                self.assertTrue(selector.menu.isVisible())
                self.assertLess(selector.menu.geometry().right(), panel.mapToGlobal(QPoint()).x())
                selector.menu.buttons[2].click()
                self.assertEqual(selector.currentIndex(), 2)
                self.assertEqual(saved[-1], panel.values())
                selector.hidePopup()
                QTest.qWait(400)
                self.assertFalse(selector.menu.isVisible())
            count = len(saved)
            panel.position.showPopup()
            panel.position.hidePopup()
            self.assertEqual(len(saved), count)
        finally:
            panel.close()
            panel.deleteLater()

    def test_grid_height_and_click_toggle(self):
        panel = SettingsPanel(normalize_settings({'region': 'kyiv'}))
        panel.resize(360, 290)
        panel.move(450, 0)
        panel.show()
        self.app.processEvents()
        selector = panel.queue_selector
        try:
            QTest.mouseClick(selector, Qt.MouseButton.LeftButton)
            QTest.qWait(400)
            self.assertTrue(selector.menu.isVisible())
            self.assertLessEqual(selector.menu.height(), panel.height())
            self.assertEqual(len(selector.menu.buttons), 60)
            self.assertGreater(selector.menu.scroll.widget().layout().columnCount(), 1)
            QTest.mouseClick(selector, Qt.MouseButton.LeftButton)
            QTest.qWait(400)
            self.assertFalse(selector.menu.isVisible())
            QTest.mouseClick(selector, Qt.MouseButton.LeftButton)
            QTest.qWait(50)
            QTest.mouseClick(selector, Qt.MouseButton.LeftButton)
            QTest.qWait(400)
            self.assertFalse(selector.menu.isVisible())
            selector.showPopup()
            QTest.qWait(400)
            selector.menu.buttons[-1].click()
            QTest.qWait(400)
            self.assertEqual(selector.currentText(), '60.1')
            self.assertFalse(selector.menu.isVisible())
        finally:
            panel.close()
            panel.deleteLater()

    def test_position_grid_matches_screen_directions(self):
        panel = SettingsPanel(normalize_settings({}))
        panel.resize(360, 530)
        panel.move(450, 0)
        panel.show()
        try:
            selector = panel.position
            self.assertEqual([selector.itemData(i) for i in range(selector.count())],
                             ['top-left', 'top', 'top-right', 'bottom-left', 'bottom', 'bottom-right'])
            selector.showPopup()
            QTest.qWait(400)
            grid = selector.menu.scroll.widget().layout()
            self.assertEqual(grid.columnCount(), 3)
            self.assertEqual(grid.rowCount(), 2)
            selector.menu.buttons[4].click()
            self.assertEqual(panel.values()['overlay_position'], 'bottom')
            self.assertEqual(normalize_settings(panel.values())['overlay_position'], 'bottom')
        finally:
            panel.close()
            panel.deleteLater()

    def test_reveal_keeps_native_canvas_and_content_size_fixed(self):
        panel = SettingsPanel(normalize_settings({}))
        panel.resize(360, 530)
        panel.move(450, 0)
        panel.show()
        self.app.processEvents()
        try:
            for selector in (panel.region_selector, panel.queue_selector, panel.position):
                selector.showPopup()
                menu = selector.menu
                canvas = QRect(menu.target)
                menu.panel_animation.pause()
                for time in (65, 130, 195, 260):
                    menu.panel_animation.setCurrentTime(time)
                    fraction = menu.panel_animation.easingCurve().valueForProgress(time / 260)
                    width = round(canvas.width() * fraction)
                    self.assertEqual(menu.geometry(), canvas)
                    self.assertEqual(menu.scroll.size(), canvas.size())
                    self.assertEqual(menu.clip.width(), width)
                    self.assertEqual(menu.clip.x(), canvas.width() - width)
                    self.assertEqual(menu.scroll.pos(), QPoint())
                menu.dismiss()
                menu.panel_animation.pause()
                menu.panel_animation.setCurrentTime(130)
                halfway = menu.reveal
                self.assertEqual(menu.geometry(), canvas)
                selector.showPopup()
                self.assertEqual(menu.reveal, halfway)
                menu.dismiss(animated=False)
        finally:
            panel.close()
            panel.deleteLater()
