"""Portable application entry point."""
import sys
from pathlib import Path


if __name__ == "__main__":
    if getattr(sys, 'frozen', False) and (Path(sys.executable).parent / '.update-in-progress').exists():
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, 'Триває оновлення програми. Зачекайте завершення.\nЯкщо оновлення було перервано вимкненням ПК, дивіться README.txt: відновлення оновлення.', 'BlackoutTracker', 0x40)
        raise SystemExit(0)
    from blackout_tracker.application import main
    raise SystemExit(main())
