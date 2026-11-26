import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from blackout_tracker.notifications import AlertState
from blackout_tracker.schedule import KYIV_TIMEZONE, parse_schedule_response
from blackout_tracker.settings import normalize_settings


class AlertTests(unittest.TestCase):
    def setUp(self):
        data = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/kyiv-region.json').read_text(encoding='utf-8'))
        self.schedule = parse_schedule_response(data, '6.1')
        self.now = datetime(2026, 11, 25, 10, 25, tzinfo=KYIV_TIMEZONE)
        self.schedule['checked'] = self.now.isoformat()
        self.alert = AlertState()

    def evaluate(self, now=None, always=False):
        return self.alert.evaluate(self.schedule, now or self.now, '6.1', always)

    def test_threshold_once_and_click_dismissal(self):
        self.assertEqual(self.evaluate(self.now - timedelta(seconds=1)), (False, None))
        self.assertEqual(self.evaluate(), (True, 5))
        self.assertEqual(self.evaluate(self.now + timedelta(seconds=1)), (True, None))
        self.alert.dismiss()
        self.assertEqual(self.evaluate(self.now + timedelta(seconds=2)), (False, None))
        self.assertEqual(self.evaluate(self.now + timedelta(minutes=5)), (False, None))

    def test_starting_inside_window(self):
        self.assertEqual(self.evaluate(self.now + timedelta(minutes=4)), (True, 5))

    def test_cancel_and_reschedule(self):
        self.evaluate()
        self.alert.dismiss()
        self.schedule['days'][0]['intervals'][1][0] = 629
        self.assertEqual(self.evaluate(), (True, 5))
        self.schedule['days'][0]['intervals'][1][0] = 660
        self.assertEqual(self.evaluate(), (False, None))

    def test_stale_and_emergency_do_not_alert(self):
        self.schedule['stale'] = True
        self.assertEqual(self.evaluate(), (False, None))
        self.schedule['stale'] = False
        self.schedule['days'][0]['status'] = 'emergency'
        self.assertEqual(self.evaluate(), (False, None))

    def test_possible_outage_and_restoration_do_not_alert(self):
        self.schedule['days'][0]['intervals'][1][2] = 'maybe'
        self.assertEqual(self.evaluate(), (False, None))
        self.schedule['days'][0]['intervals'][1][2] = 'off'
        self.schedule['checked'] = self.now.replace(hour=16, minute=55).isoformat()
        self.assertEqual(self.evaluate(self.now.replace(hour=16, minute=55)), (False, None))

    def test_permanent_overlay_dismiss_and_next_event(self):
        self.assertEqual(self.evaluate(self.now - timedelta(minutes=10), True), (True, None))
        self.alert.dismiss()
        self.assertEqual(self.evaluate(self.now - timedelta(minutes=9), True), (False, None))
        self.assertEqual(self.evaluate(self.now + timedelta(minutes=5), True), (True, None))

    def test_missing_preferences_get_defaults_and_bad_interval_rejected(self):
        defaults = normalize_settings({'group': '2.2'}, '2.2')
        self.assertTrue(defaults['overlay_topmost'])
        self.assertEqual(defaults['refresh_minutes'], 15)
        self.assertTrue(defaults['notify_5_minutes'])
        for interval in (0, 31, True, '5', None):
            self.assertEqual(normalize_settings({'refresh_minutes': interval})['refresh_minutes'], 15)
        self.assertEqual(normalize_settings({'refresh_minutes': 5})['refresh_minutes'], 5)

    def test_two_independent_thresholds_and_no_late_ten_minute_alert(self):
        ten = self.now - timedelta(minutes=5)
        self.assertEqual(self.alert.evaluate(self.schedule, ten, '6.1', notify_minutes=(5,10)), (False,10))
        self.assertIsNone(self.alert.evaluate(self.schedule, ten + timedelta(seconds=1), '6.1', notify_minutes=(5,10))[1])
        self.assertEqual(self.alert.evaluate(self.schedule, self.now, '6.1', notify_minutes=(5,10)), (True,5))
        self.assertIsNone(self.alert.evaluate(self.schedule, self.now, '6.1', notify_minutes=(5,10))[1])
        self.assertIsNone(AlertState().evaluate(self.schedule, self.now, '6.1', notify_minutes=(10,))[1])
        self.assertIsNone(AlertState().evaluate(self.schedule, self.now, '6.1', notify_minutes=())[1])

    def test_legacy_disabled_sound_is_preserved(self):
        self.assertFalse(normalize_settings({'sound_enabled':False})['notify_5_minutes'])
        self.assertFalse(normalize_settings({})['notify_10_minutes'])
