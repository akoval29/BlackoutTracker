import copy
import json
import unittest
from datetime import datetime
from pathlib import Path
from blackout_tracker.schedule import KYIV_TIMEZONE, parse_schedule_response, get_schedule_state, is_schedule_fresh

ROOT = Path(__file__).resolve().parents[1]


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / 'tests/fixtures/kyiv-region.json').read_text(encoding='utf-8'))
        self.schedule = parse_schedule_response(self.raw, '6.1')

    def at(self, day, hour, minute=0):
        return datetime(2026, 11, day, hour, minute, tzinfo=KYIV_TIMEZONE)

    def test_half_hour_intervals(self):
        self.assertEqual(self.schedule['days'][1]['intervals'], [[420, 690, 'off'], [1020, 1260, 'off']])

    def test_boundaries(self):
        self.assertIn('відключення', get_schedule_state(self.schedule, self.at(25, 10, 29))[0])
        self.assertEqual(get_schedule_state(self.schedule, self.at(25, 10, 30))[1], self.at(25, 17))
        self.assertEqual(get_schedule_state(self.schedule, self.at(25, 17))[1], self.at(25, 21))
        self.assertEqual(get_schedule_state(self.schedule, self.at(25, 23))[1], self.at(26, 0))

    def test_midnight_continuity(self):
        self.schedule['days'][1]['intervals'].insert(0, [0, 60, 'off'])
        self.assertEqual(get_schedule_state(self.schedule, self.at(25, 23))[1], self.at(26, 1))

    def test_unknown_tomorrow_does_not_promise_restoration(self):
        self.schedule['days'] = self.schedule['days'][:1]
        self.assertIsNone(get_schedule_state(self.schedule, self.at(25, 23))[1])

    def test_emergency(self):
        self.schedule['days'][0]['status'] = 'emergency'
        self.assertIsNone(get_schedule_state(self.schedule, self.at(25, 12))[1])

    def test_stale(self):
        self.assertTrue(is_schedule_fresh(self.schedule, self.at(25, 22, 48)))
        self.assertFalse(is_schedule_fresh(self.schedule, self.at(25, 23, 30)))

    def test_reject_wrong_region_and_invalid_slots(self):
        bad = copy.deepcopy(self.raw)
        bad['regionId'] = 'kyiv'
        with self.assertRaises(ValueError):
            parse_schedule_response(bad, '6.1')
        bad = copy.deepcopy(self.raw)
        next(iter(bad['fact']['data'].values()))['GPV6.1']['1'] = 'invalid'
        with self.assertRaises(ValueError):
            parse_schedule_response(bad, '6.1')


if __name__ == '__main__':
    unittest.main()
