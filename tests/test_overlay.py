import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from app import CountdownOverlay, STYLE


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def test_animation_only_on_appearance_or_selected_position_change(self):
        widget = CountdownOverlay()
        try:
            with patch.object(widget.ripple, 'start', wraps=widget.ripple.start) as start:
                widget.present('Таймер', '01:00:00', '#5ee0af', 'top')
                self.assertEqual(start.call_count, 1)
                self.assertEqual(widget.timer.scale, 0)
                widget.text_motion.setCurrentTime(210)
                self.assertGreater(widget.timer.scale, 0)
                self.assertLess(widget.timer.scale, 1)
                scale = widget.timer.scale
                width = widget.width()
                # Simulate native-window coordinate drift and varied digit widths.
                widget.move(widget.x() + 1, widget.y())
                for value in ('00:59:59', '00:59:58', '00:11:11', '00:00:00'):
                    widget.present('Таймер', value, '#f87171', 'top')
                self.assertEqual(start.call_count, 1)
                self.assertEqual(widget.timer.scale, scale)
                self.assertEqual(widget.width(), width)
                widget.text_motion.setCurrentTime(420)
                self.assertEqual(widget.timer.scale, 1)
                widget.present('Таймер', '00:59:57', '#5ee0af', 'bottom-left')
                self.assertEqual(start.call_count, 2)
                widget.hide()
                widget.present('Таймер', '00:59:56', '#5ee0af', 'bottom-left')
                self.assertEqual(start.call_count, 3)
        finally:
            widget.hide()
            widget.deleteLater()
