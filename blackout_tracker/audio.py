"""Sequential WAV playback on a background worker, without blocking Qt."""
from queue import Queue
from threading import Thread, Lock
from blackout_tracker.resources import ASSETS_DIRECTORY

_pending = Queue()
_worker = None
_lock = Lock()


def play_sequence(minutes):
    import winsound
    for filename in ('siren.wav', f'blackout_in_{minutes}.wav'):
        winsound.PlaySound(str(ASSETS_DIRECTORY / filename), winsound.SND_FILENAME | winsound.SND_SYNC | winsound.SND_NODEFAULT)


def _consume():
    while True:
        minutes = _pending.get()
        try:
            play_sequence(minutes)
        except (ImportError, RuntimeError, OSError):
            # A failed file must not prevent later notifications from playing.
            pass
        finally:
            _pending.task_done()


def play_warning(minutes=5):
    global _worker
    if minutes not in (5, 10):
        raise ValueError('Unsupported notification interval')
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = Thread(target=_consume, name='outage-audio', daemon=True)
            _worker.start()
        _pending.put(minutes)
