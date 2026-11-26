import json
import unittest
from pathlib import Path
from unittest.mock import patch
import core
from preferences import normalize_settings


class SourceTests(unittest.TestCase):
    def test_only_one_request_and_no_provider_in_warning(self):
        raw = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/kyiv-region.json').read_text(encoding='utf-8'))
        with patch('core.fresh', return_value=True), patch('core.datetime') as dt, patch('core.read_json', return_value=raw) as read:
            from datetime import datetime
            dt.now.return_value = datetime(2026,11,25,tzinfo=core.KYIV)
            dt.fromtimestamp = datetime.fromtimestamp
            dt.strptime = datetime.strptime
            dt.fromisoformat = datetime.fromisoformat
            result = core.fetch_schedule('6.1')
            read.assert_called_once_with(core.SCHEDULE_URL)
            self.assertEqual(result['warning'], '')

    def test_error_does_not_leak_url_and_no_fallback(self):
        with patch('core.read_json', side_effect=OSError('https://example.invalid')) as read:
            with self.assertRaises(ValueError) as error:
                core.fetch_schedule('6.1')
            self.assertNotIn('https', str(error.exception))
            self.assertEqual(read.call_count, 1)

    def test_sound_allowlist(self):
        self.assertEqual(normalize_settings({'sound_name':'siren'})['sound_name'], 'siren')
        self.assertEqual(normalize_settings({'sound_name':'../file'})['sound_name'], 'warning')
