import os
import unittest
from datetime import datetime
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from blackout_tracker.ui.schedule_chart import day_segments, ScheduleChart, ScheduleIntervalBlock


class SegmentTests(unittest.TestCase):
    def test_covers_day_and_preserves_half_hour_boundaries(self):
        day = {'status': 'scheduled', 'intervals': [[420, 690, 'off'], [1020, 1260, 'off']]}
        self.assertEqual(day_segments(day), [
            [0, 420, 'on'], [420, 690, 'off'], [690, 1020, 'on'],
            [1020, 1260, 'off'], [1260, 1440, 'on']])

    def test_four_periods_and_adjacent_merge(self):
        day = {'status': 'scheduled', 'intervals': [[0, 60, 'off'], [60, 90, 'off'], [600, 660, 'off']]}
        self.assertEqual(day_segments(day), [
            [0, 90, 'off'], [90, 600, 'on'], [600, 660, 'off'], [660, 1440, 'on']])

    def test_unknown_and_emergency_do_not_imply_power(self):
        self.assertEqual(day_segments(None), [])
        self.assertEqual(day_segments({'status': 'emergency'}), [])
        self.assertEqual(day_segments({'status': 'unknown'}), [])
        self.assertEqual(day_segments({'status': 'no-outages', 'intervals': []}), [[0, 1440, 'on']])


class ScheduleWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_progress_tracks_intervals_without_rebuilding_each_minute(self):
        chart = ScheduleChart()
        schedule = {'days': [
            {'date': date, 'status': 'scheduled', 'intervals': [[420, 690, 'off'], [1020, 1260, 'off']]}
            for date in ('2026-11-26', '2026-11-27')]}
        try:
            chart.set_schedule(schedule, datetime(2026, 11, 26, 19, 46))
            chart.resize(400, 180)
            chart.show()
            self.app.processEvents()
            chart.animate_wave()
            blocks = [block for block, _, _ in chart.today_blocks]
            self.assertEqual([block.elapsed_fraction for block in blocks[:3]], [1, 1, 1])
            self.assertAlmostEqual(blocks[3].elapsed_fraction, 166 / 240)
            self.assertEqual(blocks[4].elapsed_fraction, 0)
            tomorrow = [block for block in chart.findChildren(ScheduleIntervalBlock) if block not in blocks]
            self.assertTrue(all(block.elapsed_fraction == 0 for block in tomorrow))
            chart.set_schedule(schedule, datetime(2026, 11, 26, 19, 47))
            self.assertIs(chart.today_blocks[3][0], blocks[3])
            self.assertEqual(chart.day_titles[0].text(), 'Сьогодні · 26.11.26 19:47')
            chart.set_schedule(schedule, datetime(2026, 11, 26, 21, 0))
            self.assertEqual(blocks[3].elapsed_fraction, 1)
            self.assertEqual(blocks[4].elapsed_fraction, 0)
            self.assertTrue(chart.wave_timer.isActive())
            chart.hide()
            self.assertFalse(chart.wave_timer.isActive())
        finally:
            chart.close()
            chart.deleteLater()

    def test_wave_is_clipped_to_elapsed_colored_area(self):
        chart = ScheduleChart()
        try:
            chart.set_schedule({'days': [{'date': '2026-11-26', 'status': 'no-outages', 'intervals': []}]},
                               datetime(2026, 11, 26, 12))
            chart.resize(400, 90)
            chart.show()
            self.app.processEvents()
            chart.wave_timer.stop()
            block = chart.today_blocks[0][0]
            block.elapsed_fraction = 0
            baseline = chart.grab().toImage()
            block.elapsed_fraction = 0.5
            block.wave_center = block.x() + block.width() * 0.4
            block.wave_radius = block.width()
            highlighted = chart.grab().toImage()
            origin = block.mapTo(chart, block.rect().topLeft())
            self.assertNotEqual(baseline.pixelColor(origin.x() + 20, origin.y() + 6),
                                highlighted.pixelColor(origin.x() + 20, origin.y() + 6))
            for y in range(baseline.height()):
                for x in range(baseline.width()):
                    if not (origin.x() <= x < origin.x() + block.width() * 0.5
                            and origin.y() <= y < origin.y() + block.height()):
                        self.assertEqual(baseline.pixelColor(x, y), highlighted.pixelColor(x, y))
        finally:
            chart.close()
            chart.deleteLater()
