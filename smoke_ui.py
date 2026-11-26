"""Render the actual widgets offscreen using recorded API data, without user settings."""
import json
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from app import Window, Setup, STYLE
from core import normalize_github

app = QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
folder = Path('build/ui-check')
folder.mkdir(parents=True, exist_ok=True)
(folder / 'settings.json').write_text('{}', encoding='utf-8')
with patch.object(Window, 'refresh'):
    window = Window(folder, '6.1')
    window.received(normalize_github(json.loads(Path('tests/fixtures/kyiv-region.json').read_text(encoding='utf-8')), '6.1'))
    window.show()
    QTest.qWait(400)
    app.processEvents()
    window.grab().save(str(folder / 'compact.png'))
    assert not window.expanded and not window.details.isVisible()
    bottom_right = window.geometry().bottomRight()
    window.expand_button.click()
    QTest.qWait(100)
    assert window.motion.state() == window.motion.State.Running
    QTest.qWait(200)
    app.processEvents()
    assert window.expanded and window.details.isVisible()
    assert window.geometry().bottomRight() == bottom_right
    window.grab().save(str(folder / 'expanded.png'))
    window.expand_button.click()
    assert not window.expanded
    assert '6.1' in window.subtitle.text()
    assert 'Перевірено' in window.source.text()
    assert 'GitHub' not in window.source.text()
    setup = Setup('6.1')
    setup.show()
    app.processEvents()
    setup.grab().save(str(folder / 'setup.png'))
    assert setup.combo.currentText() == '6.1'
    setup.combo.setCurrentText('2.2')
    assert setup.combo.currentText() == '2.2'
    from datetime import datetime
    from core import KYIV
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    fixed_canvas = window.geometry()
    fixed_panel = window.main_panel.geometry()
    window.configure()
    for _ in range(6):
        QTest.qWait(50)
        assert window.geometry() == fixed_canvas
        assert window.main_panel.geometry() == fixed_panel
        assert window.drawer_clip.geometry().right() + 1 == window.main_panel.x()
    settings = window.settings_panel
    assert settings.topmost.isChecked()
    assert window.drawer_clip.height() == window.main_panel.height()
    assert settings.window() == window
    assert window.settings_open and window.drawer_clip.isVisible()
    assert window.geometry().bottomRight() == bottom_right
    assert window.drawer_clip.geometry().right() + 1 == window.main_panel.x()
    # Finishing must not resize/move either the native window or main panel.
    settled = (window.geometry(), window.main_panel.geometry())
    QTest.qWait(50)
    assert settled == (window.geometry(), window.main_panel.geometry())
    window.grab().save(str(folder / 'settings.png'))
    settings.sound_choice.setCurrentIndex(settings.sound_choice.findData('siren'))
    settings.interval.setValue(7)
    settings.topmost.setChecked(False)
    assert window.settings_open
    assert not window.preferences["overlay_topmost"]
    window.close_settings()
    QTest.qWait(300)
    assert window.preferences['sound_name'] == 'siren'
    window.toggle_expanded()
    QTest.qWait(50)
    window.toggle_expanded()
    QTest.qWait(300)
    assert not window.expanded
    assert window.main_panel.height() == 240
    assert window.poll_timer.interval() == 420000
    assert not json.loads((folder / 'settings.json').read_text(encoding='utf-8'))['overlay_topmost']
    window.configure()
    QTest.qWait(300)
    with patch('app.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
        window.hide_to_tray()
        QTest.qWait(400)
    assert not window.isVisible()
    window.reveal()
    window.close_settings()
    QTest.qWait(300)
    schedule = normalize_github(json.loads(Path('tests/fixtures/kyiv-region.json').read_text(encoding='utf-8')), '6.1')
    now = datetime(2026, 11, 25, 10, 25, tzinfo=KYIV)
    schedule['checked'] = now.isoformat()
    with patch('app.datetime') as clock, patch('app.play_warning') as sound:
        clock.now.return_value = now
        window.received(schedule)
        assert window.overlay.isVisible()
        assert window.overlay.timer.text() == '00:05:00'
        assert window.widget_button.text() == 'Віджет: вкл'
        assert sound.call_count == 1
        window.tick()
        assert sound.call_count == 1
        app.processEvents()
        window.overlay.grab().save(str(folder / 'overlay.png'))
        QTest.mouseClick(window.overlay, Qt.MouseButton.LeftButton)
        window.tick()
        assert not window.overlay.isVisible()
        assert sound.call_count == 1
        assert window.widget_button.text() == 'Віджет: викл'
        window.widget_button.click()
        assert window.overlay.isVisible()
        assert window.widget_button.text() == 'Віджет: вкл'
        window.tick()
        assert window.overlay.isVisible()
        window.widget_button.click()
        window.tick()
        assert not window.overlay.isVisible()
        assert window.widget_button.text() == 'Віджет: викл'
        assert sound.call_count == 1
    window.overlay.hide()
    window.tray.hide()
print('UI smoke checks passed')
