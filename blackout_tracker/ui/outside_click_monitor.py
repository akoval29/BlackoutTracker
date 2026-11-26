import sys
from PySide6.QtCore import QObject, QTimer, QPoint, Signal


class OutsideClickMonitor(QObject):
    """Observe mouse button edges on Windows without intercepting input."""
    pressed = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.poll)
        self.down = set()
        self.user32 = None
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            self.ctypes = ctypes
            self.point_type = wintypes.POINT
            self.user32 = ctypes.WinDLL('user32', use_last_error=True)
            self.user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            self.user32.GetAsyncKeyState.restype = ctypes.c_short
            self.user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
            self.user32.GetCursorPos.restype = wintypes.BOOL

    def start(self):
        if self.user32:
            self.down = {key for key in (1, 2, 4) if self.user32.GetAsyncKeyState(key) & 0x8000}
            self.timer.start()

    def stop(self):
        self.timer.stop()

    def poll(self):
        down = {key for key in (1, 2, 4) if self.user32.GetAsyncKeyState(key) & 0x8000}
        new_press = down - self.down
        self.down = down
        if new_press:
            point = self.point_type()
            if self.user32.GetCursorPos(self.ctypes.byref(point)):
                self.pressed.emit(QPoint(point.x, point.y))
