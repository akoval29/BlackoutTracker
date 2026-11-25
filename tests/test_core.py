import copy
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from core import KYIV, normalize_gpv, normalize_github, state_at, fresh, fetch_schedule

ROOT = Path(__file__).resolve().parents[1]


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / 'gpv-6.1.json').read_text(encoding='utf-8'))
        self.schedule = normalize_gpv(self.raw, '6.1')

    def at(self, day, hour, minute=0):
        return datetime(2026, 11, day, hour, minute, tzinfo=KYIV)

    def test_two_sources_agree(self):
        backup = normalize_github(json.loads((ROOT / 'kyiv-region.json').read_text(encoding='utf-8')), '6.1')
        self.assertEqual(self.schedule['days'], backup['days'])

    def test_boundaries(self):
        self.assertIn('відключення', state_at(self.schedule, self.at(25, 10, 29))[0])
        self.assertEqual(state_at(self.schedule, self.at(25, 10, 30))[1], self.at(25, 17))
        self.assertEqual(state_at(self.schedule, self.at(25, 17))[1], self.at(25, 21))
        self.assertEqual(state_at(self.schedule, self.at(25, 23))[1], self.at(26, 0))

    def test_midnight_continuity(self):
        self.schedule['days'][1]['intervals'].insert(0, [0, 60, 'off'])
        self.assertEqual(state_at(self.schedule, self.at(25, 23))[1], self.at(26, 1))

    def test_unknown_tomorrow_does_not_promise_restoration(self):
        self.schedule['days'] = self.schedule['days'][:1]
        self.assertIsNone(state_at(self.schedule, self.at(25, 23))[1])

    def test_emergency(self):
        self.schedule['days'][0]['status'] = 'emergency'
        self.assertIsNone(state_at(self.schedule, self.at(25, 12))[1])

    def test_stale(self):
        self.assertTrue(fresh(self.schedule, self.at(25, 22, 48)))
        self.assertFalse(fresh(self.schedule, self.at(25, 23, 30)))

    def test_reject_wrong_region_and_invalid_slots(self):
        bad = copy.deepcopy(self.raw)
        bad['region']['slug'] = 'kyiv'
        with self.assertRaises(ValueError):
            normalize_gpv(bad, '6.1')
        bad = copy.deepcopy(self.raw)
        bad['days'][0]['intervals'][0] = [180, 0, 'off']
        with self.assertRaises(ValueError):
            normalize_gpv(bad, '6.1')

    def test_fallback_when_primary_fails(self):
        backup = json.loads((ROOT / 'kyiv-region.json').read_text(encoding='utf-8'))
        with patch('core.read_json', side_effect=[OSError('offline'), backup]), patch('core.fresh', return_value=True), patch('core.datetime') as dt:
            dt.now.return_value = self.at(25, 22, 48)
            dt.fromtimestamp = datetime.fromtimestamp
            dt.strptime = datetime.strptime
            dt.fromisoformat = datetime.fromisoformat
            result = fetch_schedule('6.1')
        self.assertIn('GitHub', result['source'])


if __name__ == '__main__':
    unittest.main()
