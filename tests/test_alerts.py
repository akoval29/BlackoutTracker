import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from alerts import AlertState
from core import KYIV, normalize_github
from preferences import normalize_settings


class AlertTests(unittest.TestCase):
    def setUp(self):
        data = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/kyiv-region.json').read_text(encoding='utf-8'))
        self.schedule = normalize_github(data, '6.1')
        self.now = datetime(2026, 11, 25, 10, 25, tzinfo=KYIV)
        self.schedule['checked'] = self.now.isoformat()
        self.alert = AlertState()

    def evaluate(self, now=None, always=False):
        return self.alert.evaluate(self.schedule, now or self.now, '6.1', always)

    def test_threshold_once_and_click_dismissal(self):
        self.assertEqual(self.evaluate(self.now - timedelta(seconds=1)), (False, False))
        self.assertEqual(self.evaluate(), (True, True))
        self.assertEqual(self.evaluate(self.now + timedelta(seconds=1)), (True, False))
        self.alert.dismiss()
        self.assertEqual(self.evaluate(self.now + timedelta(seconds=2)), (False, False))
        self.assertEqual(self.evaluate(self.now + timedelta(minutes=5)), (False, False))

    def test_starting_inside_window(self):
        self.assertEqual(self.evaluate(self.now + timedelta(minutes=4)), (True, True))

    def test_cancel_and_reschedule(self):
        self.evaluate()
        self.alert.dismiss()
        self.schedule['days'][0]['intervals'][1][0] = 629
        self.assertEqual(self.evaluate(), (True, True))
        self.schedule['days'][0]['intervals'][1][0] = 660
        self.assertEqual(self.evaluate(), (False, False))

    def test_stale_and_emergency_do_not_alert(self):
        self.schedule['stale'] = True
        self.assertEqual(self.evaluate(), (False, False))
        self.schedule['stale'] = False
        self.schedule['days'][0]['status'] = 'emergency'
        self.assertEqual(self.evaluate(), (False, False))

    def test_possible_outage_and_restoration_do_not_alert(self):
        self.schedule['days'][0]['intervals'][1][2] = 'maybe'
        self.assertEqual(self.evaluate(), (False, False))
        self.schedule['days'][0]['intervals'][1][2] = 'off'
        self.schedule['checked'] = self.now.replace(hour=16, minute=55).isoformat()
        self.assertEqual(self.evaluate(self.now.replace(hour=16, minute=55)), (False, False))

    def test_permanent_overlay_dismiss_and_next_event(self):
        self.assertEqual(self.evaluate(self.now - timedelta(minutes=10), True), (True, False))
        self.alert.dismiss()
        self.assertEqual(self.evaluate(self.now - timedelta(minutes=9), True), (False, False))
        self.assertEqual(self.evaluate(self.now + timedelta(minutes=5), True), (True, False))

    def test_missing_preferences_get_defaults_and_bad_interval_rejected(self):
        defaults = normalize_settings({'group': '2.2'}, '2.2')
        self.assertTrue(defaults['overlay_topmost'])
        self.assertEqual(defaults['refresh_minutes'], 15)
        self.assertTrue(defaults['sound_enabled'])
        for interval in (0, 31, True, '5', None):
            self.assertEqual(normalize_settings({'refresh_minutes': interval})['refresh_minutes'], 15)
        self.assertEqual(normalize_settings({'refresh_minutes': 5})['refresh_minutes'], 5)
