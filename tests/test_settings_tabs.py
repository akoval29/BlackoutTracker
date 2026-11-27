import os
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from blackout_tracker.settings import normalize_settings
from blackout_tracker.ui.settings_panel import SettingsPanel


class SettingsTabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_audio_language_persists_and_previews_do_not_change_it(self):
        panel = SettingsPanel(normalize_settings({'audio_language': 'de'}))
        saved = []
        panel.saved.connect(saved.append)
        try:
            self.assertEqual(panel.selected_audio_language(), 'de')
            panel.audio_language_buttons['en'].click()
            self.assertEqual(saved[-1]['audio_language'], 'en')
            preferences = normalize_settings(panel.values())
            panel.load(preferences)
            self.assertEqual(panel.selected_audio_language(), 'en')
            with patch('blackout_tracker.ui.settings_panel.play_warning') as play:
                panel.audio_previews[10].click()
                play.assert_called_with(10, 'en')
                panel.audio_previews[5].click()
                play.assert_called_with(5, 'en')
                self.assertEqual(panel.values()['audio_language'], 'en')
            with patch('blackout_tracker.ui.settings_panel.play_message') as play:
                for ident, button in panel.message_previews.items():
                    button.click()
                    play.assert_called_with(ident, 'en')
            self.assertEqual(len(panel.audio_previews) + len(panel.message_previews), 5)
            self.assertEqual(sum(b.isChecked() for b in panel.audio_language_buttons.values()), 1)
            self.assertEqual(len(saved), 1)
        finally:
            panel.deleteLater()

    def test_audio_language_defaults_and_invalid_values(self):
        for value in ({}, {'audio_language': 'xx'}, {'audio_language': None}):
            self.assertEqual(normalize_settings(value)['audio_language'], 'ua')
        for lang in ('ua', 'en', 'de'):
            self.assertEqual(normalize_settings({'audio_language': lang})['audio_language'], lang)

    def test_tabs_show_one_section_and_preserve_unswitched_values(self):
        panel = SettingsPanel(normalize_settings({}))
        panel.resize(700, 400)
        panel.show()
        self.app.processEvents()
        saved = []
        panel.saved.connect(saved.append)
        try:
            panel.interval.setValue(7)
            expected = panel.values()
            saves = len(saved)
            for index in (1, 2, 3, 4, 5, 0):
                panel.tabs.setCurrentIndex(index)
                self.app.processEvents()
                self.assertEqual([key for key, card in panel.section_cards.items() if card.isVisible()], [index])
                self.assertEqual(panel.values(), expected)
                self.assertEqual(len(saved), saves)
            panel.region_selector.showPopup()
            self.assertTrue(panel.region_selector.menu.isVisible())
            panel.tabs.setCurrentIndex(2)
            self.assertFalse(panel.region_selector.menu.isVisible())
            panel.topmost.setChecked(not panel.topmost.isChecked())
            self.assertEqual(len(saved), saves + 1)
            self.assertEqual(saved[-1], panel.values())
            # A background refresh must keep the selected page.
            panel.load(panel.values())
            self.assertEqual(panel.tabs.currentIndex(), 2)
        finally:
            panel.close()
            panel.deleteLater()
