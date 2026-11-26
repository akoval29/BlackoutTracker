"""Portable data location and atomic JSON persistence."""
import json
import os
import sys
from pathlib import Path


def save_json_atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)



def get_data_directory():
    override = os.environ.get('BLACKOUT_DATA_DIR')
    if override:
        return Path(override)
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    if (base / 'portable.flag').exists():
        return base / 'data'
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'BlackoutTracker'

