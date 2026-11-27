"""Harmless executable fixture for tools.check_updater; writes a startup receipt."""
from pathlib import Path
import sys

if __name__ == '__main__':
    Path(sys.executable).with_name('started.txt').write_text('new version started')
