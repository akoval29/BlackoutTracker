import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from blackout_tracker.ui.main_window import MainWindow
from blackout_tracker.ui.settings_panel import SettingsPanel
from blackout_tracker.ui.setup_dialog import SetupDialog
from blackout_tracker.schedule import parse_schedule_response, fetch_schedule
from blackout_tracker.settings import normalize_settings, load_settings
from blackout_tracker.regions import REGIONS, DEFAULT_REGION, groups_for


class RegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.raw = json.loads((Path(__file__).parent / 'fixtures/kyiv-region.json').read_text(encoding='utf-8'))

    def test_urls_and_region_identity(self):
        for region in REGIONS:
            raw = copy.deepcopy(self.raw)
            raw['regionId'] = region
            with patch('blackout_tracker.schedule.read_json', return_value=raw) as read, patch('blackout_tracker.schedule.is_schedule_fresh', return_value=True):
                # Fetch may reject the fixture date; URL and normalization remain verifiable.
                try:
                    fetch_schedule('6.1', region)
                except ValueError:
                    pass
                self.assertTrue(read.call_args.args[0].endswith('/' + region + '.json'))
            self.assertEqual(parse_schedule_response(raw, '6.1', region)['region'], region)
        with self.assertRaises(ValueError):
            parse_schedule_response(self.raw, '6.1', 'odesa')

    def test_emergency_notice_not_general_advice(self):
        self.assertFalse(parse_schedule_response(self.raw, '6.1')['warning'])
        raw = copy.deepcopy(self.raw)
        raw['attention'] = {'text': 'Впровадженні екстрені відключення світла. Графіки тут не працюють.'}
        result = parse_schedule_response(raw, '6.1')
        self.assertTrue(result['warning'])
        self.assertIn('emergency', [day['status'] for day in result['days']])

    def test_legacy_settings_and_group_catalog(self):
        self.assertEqual(normalize_settings({})['region'], DEFAULT_REGION)
        self.assertEqual(len(groups_for('kyiv')), 60)
        self.assertEqual(normalize_settings({'region': 'kyiv'}, '60.1')['group'], '60.1')
        self.assertEqual(normalize_settings({'region': 'odesa'}, '60.1')['group'], '1.1')
        self.assertEqual(normalize_settings({'region': '../bad'})['region'], DEFAULT_REGION)

    def test_live_change_cache_isolation_and_late_response(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(MainWindow, 'refresh'):
            folder = Path(directory)
            window = MainWindow(folder, '6.1')
            try:
                kyiv = parse_schedule_response(self.raw, '6.1')
                window.received(kyiv)
                self.assertTrue((folder / 'cache-kyiv-region-6.1.json').exists())
                window.settings_panel.region_selector.setCurrentIndex(2)
                self.assertEqual(window.region, 'odesa')
                self.assertIsNone(window.schedule)
                window.received(kyiv)
                self.assertIsNone(window.schedule)
                self.assertIn('Одеська', window.subtitle.text())
                raw = copy.deepcopy(self.raw)
                raw['regionId'] = 'odesa'
                window.received(parse_schedule_response(raw, '6.1', 'odesa'))
                self.assertTrue((folder / 'cache-odesa-6.1.json').exists())
                self.assertEqual(load_settings(folder / 'settings.json', '6.1')['region'], 'odesa')
                window.settings_panel.region_selector.setCurrentIndex(1)
                self.assertEqual(window.settings_panel.queue_selector.count(), 60)
                window.settings_panel.queue_selector.setCurrentText('60.1')
                window.settings_panel.region_selector.setCurrentIndex(0)
                self.assertEqual(window.group, '1.1')
                self.assertEqual(window.settings_panel.queue_selector.count(), 12)
            finally:
                window.overlay.hide()
                window.tray.hide()
                window.deleteLater()

    def test_first_run_region_updates_groups(self):
        setup = SetupDialog('6.1')
        setup.region_selector.setCurrentIndex(1)
        self.assertEqual(setup.queue_selector.count(), 60)
        setup.queue_selector.setCurrentText('60.1')
        setup.region_selector.setCurrentIndex(2)
        self.assertEqual(setup.queue_selector.currentText(), '1.1')
        setup.deleteLater()
