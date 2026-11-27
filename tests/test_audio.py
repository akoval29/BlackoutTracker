import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from blackout_tracker.audio import AudioPlayer, AUDIO_DIRECTORY, load_registry, message_paths, play_warning

class FakeOutput(QObject):
    pass

class FakePlayer(QObject):
    mediaStatusChanged = Signal(object)
    playbackStateChanged = Signal(object)
    errorOccurred = Signal(object, str)
    def setAudioOutput(self, output): pass
    def setSource(self, source): self.source = source
    def play(self):
        self.playing = True
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
    def stop(self): self.playing = False

class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_registry_translations_exist_and_match_hashes(self):
        registry = load_registry()
        self.assertEqual(len(registry['messages']), 36)
        paths = []
        for ident, message in registry['messages'].items():
            self.assertEqual(set(message['translations']), {'ua', 'en', 'de'})
            for lang, translation in message['translations'].items():
                path = message_paths(ident, lang, False)[0]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), translation['sha256'])
                paths.append(path)
        self.assertEqual(len(set(paths)), 108)

    def test_intro_and_language_aliases(self):
        for lang, alias in [('ua', 'uk-UA'), ('en', 'en-US'), ('de', 'de-DE')]:
            paths = message_paths('power.outage_in_5_minutes', alias)
            self.assertEqual(paths, [AUDIO_DIRECTORY.resolve() / lang / 'common_attention.mp3',
                                    AUDIO_DIRECTORY.resolve() / lang / 'power_outage_in_5_minutes.mp3'])
        self.assertEqual(len(message_paths('app.updated')), 1)
        self.assertEqual(len(message_paths('alert.air_raid', include_intro=False)), 1)
        with self.assertRaises(ValueError): message_paths('app.updated', 'xx')
        with self.assertRaises(KeyError): message_paths('missing')

    def make_player(self):
        player = AudioPlayer(player_factory=FakePlayer, output_factory=FakeOutput)
        self.addCleanup(player.deleteLater)
        return player

    def test_sequences_never_overlap_or_interleave(self):
        player = self.make_player(); started = []; finished = []
        activity = []
        player.activity_changed.connect(activity.append)
        player.clip_started.connect(started.append); player.clip_finished.connect(finished.append)
        first = message_paths('power.outage_in_5_minutes')
        second = message_paths('power.outage_in_10_minutes')
        player.enqueue(first); player.enqueue(second)
        self.assertEqual(started, [str(first[0])])
        for path in first + second:
            self.assertEqual(started[-1], str(path))
            player._active.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
            self.app.processEvents()
        self.assertEqual(started, [str(p) for p in first + second])
        self.assertEqual(finished, started)
        self.assertIsNone(player._active)
        self.assertEqual(activity, [True, False])
        self.assertFalse(player.is_active)

    def test_error_and_duplicate_terminal_signal_advance_once(self):
        player = self.make_player(); failed = []
        player.clip_failed.connect(lambda path, error: failed.append(path))
        player.enqueue([Path('bad.mp3'), Path('good.mp3')]); old = player._active
        old.errorOccurred.emit(None, 'Decode failed')
        player._status(old, QMediaPlayer.MediaStatus.InvalidMedia)
        self.app.processEvents()
        self.assertEqual(len(failed), 1)
        self.assertEqual(player._path, Path('good.mp3'))
        player._finish(old)
        self.assertIsNotNone(player._active)
        player._finish(player._active); self.app.processEvents()
        self.assertFalse(player.is_active)

    def test_timeout_does_not_block_next_message(self):
        player = self.make_player()
        player.enqueue([Path('stuck.mp3'), Path('next.mp3')])
        player._timed_out(); self.app.processEvents()
        self.assertEqual(player._path, Path('next.mp3'))
        player._finish(player._active); self.app.processEvents()

    def test_existing_warning_entry_point_uses_registry(self):
        with patch('blackout_tracker.audio.play_message') as play:
            for minutes in (5, 10):
                self.assertTrue(play_warning(minutes))
                play.assert_called_with(f'power.outage_in_{minutes}_minutes', 'ua')
        with self.assertRaises(ValueError): play_warning(7)
