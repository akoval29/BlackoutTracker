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
                window.configure()
                QTest.qWait(300)
                window.show_journal()
                QTest.qWait(600)
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
                title = next(label for label in panel.findChildren(QLabel) if label.text() == 'Журнал подій')
                title_position = title.mapToGlobal(QPoint())
                scrollbar = panel.history.verticalScrollBar()
                self.assertTrue(scrollbar.isVisible())
                scrollbar.setValue(scrollbar.maximum())
                app.processEvents()
                self.assertEqual(title.mapToGlobal(QPoint()), title_position)
                self.assertEqual(panel.height(), window.drawer_clip.height())
                window.event_journal.events = []
                panel.refresh(window.event_journal)
                QTest.qWait(100)
                self.assertFalse(scrollbar.isVisible())
            finally:
                window.event_toast.stop()
                window.tray.hide()
                window.hide()
                window.deleteLater()
