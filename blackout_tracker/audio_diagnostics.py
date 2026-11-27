"""Muted end-to-end MP3 check, also callable from a frozen application."""
import json
from pathlib import Path
from PySide6.QtCore import QTimer
from blackout_tracker.audio import AudioPlayer, message_paths


def run_audio_check(app, report_path):
    player = AudioPlayer(app)
    player.output.setMuted(True)
    paths = [path for language in ('ua', 'en', 'de')
             for minutes in (5, 10)
             for path in message_paths(f'power.outage_in_{minutes}_minutes', language)]
    result = {'expected': [str(p) for p in paths], 'started': [], 'finished': [], 'errors': [], 'activity': []}
    player.activity_changed.connect(result['activity'].append)
    player.clip_started.connect(result['started'].append)
    player.clip_finished.connect(result['finished'].append)
    player.clip_failed.connect(lambda path, error: result['errors'].append({'path': path, 'error': error}))
    completed = False

    def finish(timed_out=False):
        nonlocal completed
        if completed:
            return
        completed = True
        result['ok'] = (not timed_out and not result['errors'] and result['finished'] == result['expected']
                        and result['activity'] == [True, False])
        result['timedOut'] = timed_out
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        app.exit(0 if result['ok'] else 1)

    player.drained.connect(finish)
    QTimer.singleShot(90000, lambda: finish(True))
    QTimer.singleShot(0, lambda: player.enqueue(paths))
    return app.exec()
