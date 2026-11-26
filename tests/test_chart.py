import unittest
from schedule_chart import day_segments


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
