"""Registry-based MP3 playback, serialized on the Qt application thread."""
from collections import deque
from functools import lru_cache
import json
import logging
from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from blackout_tracker.resources import ASSETS_DIRECTORY

log = logging.getLogger(__name__)
AUDIO_DIRECTORY = ASSETS_DIRECTORY / 'audio'

@lru_cache(maxsize=1)
def load_registry():
    registry = json.loads((AUDIO_DIRECTORY / 'registry.json').read_text(encoding='utf-8'))
    if registry['schemaVersion'] != 1:
        raise ValueError('Unsupported audio registry version')
    return registry

def message_paths(message_id, language='ua', include_intro=True):
    """Resolve the whole sequence before queueing; never play half a request."""
    registry = load_registry()
    language = {'uk': 'ua', **{v: k for k, v in registry['localeMap'].items()}}.get(language, language)
    if language not in registry['languages']:
        raise ValueError(f'Unsupported audio language: {language}')
    message = registry['messages'][message_id]
    ids = ([message['introId']] if include_intro and message['introId'] else []) + [message_id]
    root = AUDIO_DIRECTORY.resolve()
    paths = []
    for ident in ids:
        path = (root / registry['messages'][ident]['translations'][language]['path']).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != '.mp3':
            raise ValueError('Invalid audio path')
        if not path.is_file():
            raise FileNotFoundError(path)
        paths.append(path)
    return paths

class AudioPlayer(QObject):
    clip_started = Signal(str)
    clip_finished = Signal(str)
    clip_failed = Signal(str, str)
    drained = Signal()
    activity_changed = Signal(bool)

    def __init__(self, parent=None, player_factory=QMediaPlayer, output_factory=QAudioOutput):
        super().__init__(parent)
        self._factory = player_factory
        self.output = output_factory(self)
        self._pending = deque()
        self._active = None
        self._path = None
        self._advancing = False
        self.is_active = False
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._timed_out)

    def enqueue(self, paths):
        if QThread.currentThread() != self.thread():
            raise RuntimeError('Audio must be queued on the Qt application thread')
        self._pending.extend(paths)
        if self._active is None and not self._advancing:
            self._next()

    def _next(self):
        self._advancing = False
        if not self._pending:
            self._set_activity(False)
            self.drained.emit()
            return
        self._path = self._pending.popleft()
        # New instance isolates late error/end signals from the following clip.
        player = self._factory(self)
        self._active = player
        player.setAudioOutput(self.output)
        player.playbackStateChanged.connect(lambda state: self._playback_state(player, state))
        player.mediaStatusChanged.connect(lambda status: self._status(player, status))
        player.errorOccurred.connect(lambda _error, text: self._finish(player, text or 'Playback error'))
        self._timeout.start(60000)
        player.setSource(QUrl.fromLocalFile(str(self._path)))
        if self._active is player:
            self.clip_started.emit(str(self._path))
            player.play()

    def _set_activity(self, active):
        if self.is_active != active:
            self.is_active = active
            self.activity_changed.emit(active)

    def _playback_state(self, player, state):
        if player is self._active and state == QMediaPlayer.PlaybackState.PlayingState:
            self._set_activity(True)

    def _status(self, player, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._finish(player)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._finish(player, 'Invalid audio media')

    def _timed_out(self):
        if self._active is not None:
            self._finish(self._active, 'Audio playback timed out')

    def _finish(self, player, error=None):
        if player is not self._active:
            return
        path = str(self._path)
        self._active = None
        self._advancing = True
        self._timeout.stop()
        player.stop()
        player.deleteLater()
        if error:
            log.warning('Audio playback failed for %s: %s', path, error)
            self.clip_failed.emit(path, error)
        else:
            self.clip_finished.emit(path)
        QTimer.singleShot(0, self._next)

def get_player():
    app = QCoreApplication.instance()
    if app is None or QThread.currentThread() != app.thread():
        raise RuntimeError('Audio playback requires the Qt application thread')
    if not hasattr(app, '_notification_audio'):
        app._notification_audio = AudioPlayer(app)
    return app._notification_audio

def play_message(message_id, language='ua', include_intro=True):
    get_player().enqueue(message_paths(message_id, language, include_intro))

def play_warning(minutes=5, language='ua'):
    """Existing alert and preview buttons keep this entry point."""
    if minutes not in (5, 10):
        raise ValueError('Unsupported notification interval')
    try:
        play_message(f'power.outage_in_{minutes}_minutes', language)
        return True
    except (OSError, ValueError, KeyError, RuntimeError):
        log.exception('Cannot queue outage audio')
        return False
