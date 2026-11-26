"""Shared colors and control appearance for the desktop interface."""
APP_STYLESHEET = '''
QWidget { background: #202b3b; color: #f2f6fc; font-family: "Segoe UI"; font-size: 14px; }
QLabel { background: transparent; }
QFrame#card { background: #2a384b; border: 1px solid #51657f; border-radius: 14px; }
QPushButton { background: #3b506a; padding: 9px 15px; border: 1px solid #60758f; border-radius: 7px; }
QPushButton:hover { background: #4a6483; border-color: #8ba5c6; }
QPushButton:pressed { background: #30425a; border-color: #a7bdd8; }
QPushButton:focus { border-color: #a7bdd8; }
QPushButton:disabled { color: #9baac0; background: #304057; }
QComboBox, QSpinBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1e2a3b, stop:0.16 #2b3b50, stop:0.75 #32465f, stop:1 #384d67);
    padding: 9px 10px; border: 1px solid #526985;
    border-top-color: #172333; border-bottom-color: #7186a0; border-radius: 7px;
    selection-background-color: #56799d;
}
QComboBox:hover, QSpinBox:hover { border-left-color: #8ba5c6; border-right-color: #8ba5c6; }
QComboBox:focus, QSpinBox:focus { border: 1px solid #9bbadf; }
QComboBox::drop-down { border: none; width: 0px; background: transparent; }
QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
QComboBox QAbstractItemView { background: #2b394c; selection-background-color: #4a6483; border: 1px solid #60758f; }
QSpinBox { padding: 2px 4px; min-height: 26px; }
QSpinBox::up-button, QSpinBox::down-button { width: 0px; height: 0px; border: none; }
QSpinBox::up-arrow, QSpinBox::down-arrow { image: none; }
QSpinBox QLineEdit { background: transparent; border: none; padding: 0px; }
QCheckBox { background: transparent; spacing: 7px; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #7186a0; border-radius: 3px; background: #233044; }
QCheckBox::indicator:checked { background: #78e1c4; border-color: #a2f5de; image: url("CHECKMARK_ASSET"); }
QCheckBox::indicator:hover { border-color: #b5cce8; }
QLabel#muted { color: #c0ccdc; }
QMenu { background: #2b394c; border: 1px solid #60758f; padding: 6px; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background: #4a6483; }
QToolTip { background: #34485f; color: #f2f6fc; border: 1px solid #7186a0; padding: 5px; }
'''

from blackout_tracker.resources import ASSETS_DIRECTORY
APP_STYLESHEET = APP_STYLESHEET.replace('CHECKMARK_ASSET', (ASSETS_DIRECTORY / 'checkmark.svg').as_posix())

GRADIENT_DIVIDER_STYLE = (
    'border: none; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, '
    'stop:0 #60758f, stop:1 rgba(96,117,143,0));'
)

JOURNAL_SCROLLBAR_STYLE = '''
QScrollBar:vertical { background: #263448; width: 10px; margin: 0px; border-radius: 5px; }
QScrollBar::handle:vertical { background: #7189a6; min-height: 36px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #9cb8d9; }
QScrollBar::handle:vertical:pressed { background: #bad1ed; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
'''
