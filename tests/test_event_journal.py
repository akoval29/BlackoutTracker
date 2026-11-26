import unittest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from blackout_tracker.event_journal import EventJournal
from blackout_tracker.schedule import KYIV_TIMEZONE


class EventJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'events.json'
        self.journal = EventJournal(self.path)
        self.now = datetime(2026, 11, 26, 12, tzinfo=KYIV_TIMEZONE)

    def schedule(self, status='scheduled', end=600, region='kyiv-region'):
        return {'region': region, 'group': '6.1', 'days': [
            {'date': '2026-11-26', 'status': status, 'intervals': [[420, end, 'off']]}]}

    def test_initial_baseline_changes_and_restart_deduplication(self):
        self.assertEqual(self.journal.observe(self.schedule(), self.now), [])
        events = self.journal.observe(self.schedule(end=660), self.now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Змінено графік')
        self.assertEqual(events[0]['before']['intervals'][0][1], 600)
        restarted = EventJournal(self.path)
        self.assertEqual(restarted.observe(self.schedule(end=660), self.now), [])
        self.assertEqual(len(restarted.events), 1)

    def test_emergency_and_return_to_plan(self):
        self.assertEqual(self.journal.observe(self.schedule('emergency'), self.now)[0]['title'], 'Екстрені відключення')
        self.assertEqual(self.journal.observe(self.schedule('emergency'), self.now), [])
        self.assertEqual(self.journal.observe(self.schedule(), self.now)[0]['title'], 'Повернення до планового графіка')

    def test_selection_isolation_publication_and_date_rollover(self):
        self.journal.observe(self.schedule(), self.now)
        self.assertEqual(self.journal.observe(self.schedule(region='kyiv'), self.now), [])
        updated = self.schedule()
        updated['days'].append({'date': '2026-11-27', 'status': 'no-outages', 'intervals': []})
        self.assertEqual(self.journal.observe(updated, self.now)[0]['title'], 'Опубліковано графік')
        updated['days'].pop(0)
        tomorrow = self.now.replace(day=27)
        self.assertEqual(self.journal.observe(updated, tomorrow), [])

    def test_existing_cache_is_baseline(self):
        events = self.journal.observe(self.schedule(end=660), self.now, self.schedule())
        self.assertEqual(len(events), 1)

    def test_clear_persists_and_keeps_change_detection_baseline(self):
        self.journal.observe(self.schedule('emergency'), self.now)
        self.assertTrue(self.journal.clear())
        restarted = EventJournal(self.path)
        self.assertEqual(restarted.events, [])
        self.assertEqual(restarted.observe(self.schedule('emergency'), self.now), [])
        self.assertEqual(restarted.observe(self.schedule(), self.now)[0]['title'], 'Повернення до планового графіка')

    def test_clear_failure_preserves_events(self):
        self.journal.observe(self.schedule('emergency'), self.now)
        with patch('blackout_tracker.event_journal.save_json_atomic', side_effect=OSError):
            self.assertFalse(self.journal.clear())
        self.assertEqual(len(self.journal.events), 1)
        self.assertTrue(self.journal.error)
