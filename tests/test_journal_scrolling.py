import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea
from PySide6.QtTest import QTest
from blackout_tracker.ui.main_window import MainWindow


class JournalScrollingTests(unittest.TestCase):
    def test_settings_to_journal_has_only_inner_scroll_and_fixed_title(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder, patch.object(MainWindow, 'refresh'):
            window = MainWindow(Path(folder), '6.1')
            window.tick_timer.stop()
            try:
                window.show()
                QTest.qWait(300)
                main_geometry = window.main_panel.geometry()
                window.configure()
                QTest.qWait(300)
                self.assertEqual(window.main_panel.geometry(), main_geometry)
                window.show_journal()
                QTest.qWait(600)
                self.assertEqual(window.main_panel.geometry(), main_geometry)
                panel = window.journal_panel
                parent = panel.parentWidget()
                while parent:
                    self.assertNotIsInstance(parent, QScrollArea)
                    parent = parent.parentWidget()
                self.assertFalse(panel.history.verticalScrollBar().isVisible())
                event = {'time': '2026-11-26T15:42:09+02:00', 'title': 'Змінено графік',
                         'region': 'kyiv-region', 'group': '6.1', 'date': '2026-11-26',
                         'before': None, 'after': {'status': 'scheduled', 'intervals': [[420, 690, 'off']]}}
                window.event_journal.events = [dict(event) for _ in range(30)]
                panel.refresh(window.event_journal)
                app.processEvents()
                window.update_content_height()
                QTest.qWait(400)
                self.assertEqual(window.main_panel.geometry(), main_geometry)
                title = next(label for label in panel.findChildren(QLabel) if label.text() == 'Журнал подій')
                title_position = title.mapToGlobal(QPoint())
                scrollbar = panel.history.verticalScrollBar()
                self.assertTrue(scrollbar.isVisible())
                scrollbar.setValue(scrollbar.maximum())
                app.processEvents()
                self.assertEqual(title.mapToGlobal(QPoint()), title_position)
                self.assertEqual(panel.height(), window.drawer_clip.height())
                history_height = panel.history.height()
                window.toggle_expanded()
                QTest.qWait(300)
                expanded_geometry = window.main_panel.geometry()
                self.assertGreater(expanded_geometry.height(), main_geometry.height())
                self.assertEqual(panel.height(), expanded_geometry.height())
                self.assertGreater(panel.history.height(), history_height)
                window.configure()
                QTest.qWait(600)
                self.assertEqual(window.main_panel.geometry(), expanded_geometry)
                self.assertEqual(window.settings_scroll.height(), expanded_geometry.height())
                window.show_journal()
                QTest.qWait(600)
                self.assertEqual(window.main_panel.geometry(), expanded_geometry)
                self.assertEqual(panel.caption.text(), 'Подій: 30')
                self.assertTrue(panel.clear_button.isEnabled())
                panel.clear_button.click()
                QTest.qWait(100)
                self.assertEqual(window.event_journal.events, [])
                self.assertEqual(panel.caption.text(), 'Подій: 0')
                self.assertFalse(panel.clear_button.isEnabled())
                self.assertFalse(scrollbar.isVisible())
            finally:
                window.event_toast.stop()
                window.tray.hide()
                window.hide()
                window.deleteLater()
