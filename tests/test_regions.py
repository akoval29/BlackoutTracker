import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from app import Window, SettingsPanel, Setup
from core import normalize_github, fetch_schedule
from preferences import normalize_settings, load_settings
from regions import REGIONS, DEFAULT_REGION, groups_for


class RegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.raw = json.loads((Path(__file__).parent / 'fixtures/kyiv-region.json').read_text(encoding='utf-8'))

    def test_urls_and_region_identity(self):
        for region in REGIONS:
            raw = copy.deepcopy(self.raw)
            raw['regionId'] = region
            with patch('core.read_json', return_value=raw) as read, patch('core.fresh', return_value=True):
                # Fetch may reject the fixture date; URL and normalization remain verifiable.
                try:
                    fetch_schedule('6.1', region)
                except ValueError:
                    pass
                self.assertTrue(read.call_args.args[0].endswith('/' + region + '.json'))
            self.assertEqual(normalize_github(raw, '6.1', region)['region'], region)
        with self.assertRaises(ValueError):
            normalize_github(self.raw, '6.1', 'odesa')

    def test_emergency_notice_not_general_advice(self):
        self.assertFalse(normalize_github(self.raw, '6.1')['warning'])
        raw = copy.deepcopy(self.raw)
        raw['attention'] = {'text': 'Впровадженні екстрені відключення світла. Графіки тут не працюють.'}
        result = normalize_github(raw, '6.1')
        self.assertTrue(result['warning'])
        self.assertIn('emergency', [day['status'] for day in result['days']])

    def test_legacy_settings_and_group_catalog(self):
        self.assertEqual(normalize_settings({})['region'], DEFAULT_REGION)
        self.assertEqual(len(groups_for('kyiv')), 60)
        self.assertEqual(normalize_settings({'region': 'kyiv'}, '60.1')['group'], '60.1')
        self.assertEqual(normalize_settings({'region': 'odesa'}, '60.1')['group'], '1.1')
        self.assertEqual(normalize_settings({'region': '../bad'})['region'], DEFAULT_REGION)

    def test_live_change_cache_isolation_and_late_response(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Window, 'refresh'):
            folder = Path(directory)
            window = Window(folder, '6.1')
            try:
                kyiv = normalize_github(self.raw, '6.1')
                window.received(kyiv)
                self.assertTrue((folder / 'cache-kyiv-region-6.1.json').exists())
                window.settings_panel.region_choice.setCurrentIndex(2)
                self.assertEqual(window.region, 'odesa')
                self.assertIsNone(window.schedule)
                window.received(kyiv)
                self.assertIsNone(window.schedule)
                self.assertIn('Одеська', window.subtitle.text())
                raw = copy.deepcopy(self.raw)
                raw['regionId'] = 'odesa'
                window.received(normalize_github(raw, '6.1', 'odesa'))
                self.assertTrue((folder / 'cache-odesa-6.1.json').exists())
                self.assertEqual(load_settings(folder / 'settings.json', '6.1')['region'], 'odesa')
                window.settings_panel.region_choice.setCurrentIndex(1)
                self.assertEqual(window.settings_panel.combo.count(), 60)
                window.settings_panel.combo.setCurrentText('60.1')
                window.settings_panel.region_choice.setCurrentIndex(0)
                self.assertEqual(window.group, '1.1')
                self.assertEqual(window.settings_panel.combo.count(), 12)
            finally:
                window.overlay.hide()
                window.tray.hide()
                window.deleteLater()

    def test_first_run_region_updates_groups(self):
        setup = Setup('6.1')
        setup.region_choice.setCurrentIndex(1)
        self.assertEqual(setup.combo.count(), 60)
        setup.combo.setCurrentText('60.1')
        setup.region_choice.setCurrentIndex(2)
        self.assertEqual(setup.combo.currentText(), '1.1')
        setup.deleteLater()
