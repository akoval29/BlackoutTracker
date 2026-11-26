"""Asset paths shared by source and PyInstaller builds."""
from pathlib import Path
from PySide6.QtGui import QIcon

ASSETS_DIRECTORY = Path(__file__).resolve().parent.parent / 'assets'


def load_app_icon():
    return QIcon(str(ASSETS_DIRECTORY / 'app-icon.ico'))
