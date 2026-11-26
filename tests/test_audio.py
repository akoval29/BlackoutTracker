import unittest
import wave
from unittest.mock import patch, call
import winsound
from blackout_tracker.audio import play_sequence
from blackout_tracker.resources import ASSETS_DIRECTORY


class AudioTests(unittest.TestCase):
    def test_siren_finishes_before_voice_for_both_thresholds(self):
        for minutes in (5, 10):
            with patch.object(winsound, 'PlaySound') as play:
                play_sequence(minutes)
                flags = winsound.SND_FILENAME | winsound.SND_SYNC | winsound.SND_NODEFAULT
                self.assertEqual(play.call_args_list, [
                    call(str(ASSETS_DIRECTORY / 'siren.wav'), flags),
                    call(str(ASSETS_DIRECTORY / f'blackout_in_{minutes}.wav'), flags)])

    def test_converted_audio_is_nonempty_pcm(self):
        for name in ('siren', 'blackout_in_5', 'blackout_in_10'):
            with wave.open(str(ASSETS_DIRECTORY / (name + '.wav')), 'rb') as audio:
                self.assertEqual(audio.getcomptype(), 'NONE')
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertGreater(audio.getnframes(), 0)
