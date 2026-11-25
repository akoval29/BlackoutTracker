"""Render the actual widgets offscreen using recorded API data, without user settings."""
import json
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from app import Window, Setup, STYLE
from core import normalize_gpv

app = QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
folder = Path('build/ui-check')
folder.mkdir(parents=True, exist_ok=True)
with patch.object(Window, 'refresh'):
    window = Window(folder, '6.1')
    window.received(normalize_gpv(json.loads(Path('gpv-6.1.json').read_text(encoding='utf-8')), '6.1'))
    window.show()
    app.processEvents()
    window.grab().save(str(folder / 'compact.png'))
    assert not window.expanded and not window.details.isVisible()
    bottom_right = window.geometry().bottomRight()
    window.expand_button.click()
    app.processEvents()
    assert window.expanded and window.details.isVisible()
    assert window.geometry().bottomRight() == bottom_right
    window.grab().save(str(folder / 'expanded.png'))
    window.expand_button.click()
    assert not window.expanded
    assert '6.1' in window.subtitle.text()
    assert 'GPV-UA' in window.source.text()
    setup = Setup('6.1')
    setup.show()
    app.processEvents()
    setup.grab().save(str(folder / 'setup.png'))
    assert setup.combo.currentText() == '6.1'
    setup.combo.setCurrentText('2.2')
    assert setup.combo.currentText() == '2.2'
    window.tray.hide()
print('UI smoke checks passed')
