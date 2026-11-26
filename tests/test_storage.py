import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from blackout_tracker.storage import get_data_directory


class StorageTests(unittest.TestCase):
    def test_portable_uses_executable_directory_not_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'portable.flag').write_text('portable')
            with patch.dict(os.environ, {'BLACKOUT_DATA_DIR': ''}), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(base / 'BlackoutTracker.exe')):
                self.assertEqual(get_data_directory(), base / 'data')

    def test_installed_uses_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'BLACKOUT_DATA_DIR': '', 'LOCALAPPDATA': directory}), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(Path(directory) / 'BlackoutTracker.exe')):
                self.assertEqual(get_data_directory(), Path(directory) / 'BlackoutTracker')
