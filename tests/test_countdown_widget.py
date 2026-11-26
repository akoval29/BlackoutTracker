import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from blackout_tracker.ui.countdown_widget import CountdownWidget
from blackout_tracker.ui.theme import APP_STYLESHEET


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLESHEET)

    def test_animation_only_on_appearance_or_selected_position_change(self):
        widget = CountdownWidget()
        try:
            with patch.object(widget.ripple, 'start', wraps=widget.ripple.start) as start:
                widget.present('Таймер', '01:00:00', '#5ee0af', 'top')
                self.assertEqual(start.call_count, 1)
                self.assertEqual(widget.timer.scale, 0)
                widget.text_animation.setCurrentTime(210)
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
                widget.text_animation.setCurrentTime(420)
                self.assertEqual(widget.timer.scale, 1)
                widget.present('Таймер', '00:59:57', '#5ee0af', 'bottom-left')
                self.assertEqual(start.call_count, 1)
                widget.hide()
                widget.present('Таймер', '00:59:56', '#5ee0af', 'bottom-left')
                self.assertEqual(start.call_count, 2)
        finally:
            widget.hide()
            widget.deleteLater()

    def test_travel_updates_and_rapid_retarget(self):
        widget = CountdownWidget()
        try:
            widget.present('Таймер', '01:00:00', '#5ee0af', 'top-left')
            start = widget.pos()
            widget.present('Таймер', '01:00:00', '#5ee0af', 'bottom-right')
            destination = widget.position_animation.endValue()
            self.assertEqual(widget.pos(), start)
            widget.position_animation.setCurrentTime(250)
            middle = widget.pos()
            self.assertNotEqual(middle, start)
            self.assertNotEqual(middle, destination)
            widget.present('Таймер', '00:59:59', '#5ee0af', 'bottom-right')
            self.assertEqual(widget.pos(), middle)
            self.assertEqual(widget.position_animation.currentTime(), 250)
            widget.present('Таймер', '00:59:59', '#5ee0af', 'top')
            self.assertEqual(widget.position_animation.startValue(), middle)
            widget.position_animation.setCurrentTime(500)
            self.assertEqual(widget.pos(), widget.position_animation.endValue())
            self.assertEqual(widget.timer.scale, 1)
        finally:
            widget.hide()
            widget.deleteLater()
