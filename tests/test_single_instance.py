import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication

from blackout_tracker.single_instance import ActivationServer, request_activation, server_name


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_repeated_launch_activates_existing_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            server = ActivationServer(folder)
            handler = Mock()
            server.set_handler(handler)
            try:
                for count in (1, 2):
                    self.assertTrue(request_activation(folder))
                    self.app.processEvents()
                    self.assertEqual(handler.call_count, count)
            finally:
                server.close()

    def test_activation_during_setup_is_delivered_when_window_is_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            server = ActivationServer(folder)
            try:
                self.assertTrue(request_activation(folder))
                self.app.processEvents()
                handler = Mock()
                server.set_handler(handler)
                self.app.processEvents()
                handler.assert_called_once_with()
            finally:
                server.close()

    def test_data_directories_have_separate_servers(self):
        self.assertNotEqual(server_name(Path('one')), server_name(Path('two')))
