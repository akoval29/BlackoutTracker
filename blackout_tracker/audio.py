from blackout_tracker.resources import ASSETS_DIRECTORY
from PySide6.QtWidgets import QApplication


def play_warning(name='warning'):
    try:
        import winsound
        name = name if name in ('warning', 'bell', 'siren') else 'warning'
        sound = ASSETS_DIRECTORY / (name + '.wav')
        winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except (ImportError, RuntimeError):
        QApplication.beep()

