import json
import unittest
from pathlib import Path
from unittest.mock import patch
import blackout_tracker.schedule as core
from blackout_tracker.settings import normalize_settings


class SourceTests(unittest.TestCase):
    def test_only_one_request_and_no_provider_in_warning(self):
        raw = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/kyiv-region.json').read_text(encoding='utf-8'))
        with patch('blackout_tracker.schedule.is_schedule_fresh', return_value=True), patch('blackout_tracker.schedule.datetime') as dt, patch('blackout_tracker.schedule.read_json', return_value=raw) as read:
            from datetime import datetime
            dt.now.return_value = datetime(2026,11,25,tzinfo=core.KYIV_TIMEZONE)
            dt.fromtimestamp = datetime.fromtimestamp
            dt.strptime = datetime.strptime
            dt.fromisoformat = datetime.fromisoformat
            result = core.fetch_schedule('6.1')
            read.assert_called_once_with(core.SCHEDULE_URL)
            self.assertEqual(result['warning'], '')

    def test_error_does_not_leak_url_and_no_fallback(self):
        with patch('blackout_tracker.schedule.read_json', side_effect=OSError('https://example.invalid')) as read:
            with self.assertRaises(ValueError) as error:
                core.fetch_schedule('6.1')
            self.assertNotIn('https', str(error.exception))
            self.assertEqual(read.call_count, 1)

    def test_notification_options_validate_booleans(self):
        values = normalize_settings({'notify_5_minutes': False, 'notify_10_minutes': True})
        self.assertFalse(values['notify_5_minutes'])
        self.assertTrue(values['notify_10_minutes'])
        values = normalize_settings({'notify_5_minutes': 'no', 'notify_10_minutes': 1})
        self.assertTrue(values['notify_5_minutes'])
        self.assertFalse(values['notify_10_minutes'])
