"""Notify the running application when its shortcut is opened again."""
import hashlib
import os
import time

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def server_name(folder):
    path = os.path.normcase(str(folder.resolve()))
    return 'BlackoutTracker-' + hashlib.sha256(path.encode('utf-8')).hexdigest()


def request_activation(folder):
    # The lock owner may still be starting its local server.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        socket = QLocalSocket()
        socket.connectToServer(server_name(folder))
        if socket.waitForConnected(100):
            socket.disconnectFromServer()
            return True
        socket.abort()
        time.sleep(0.05)
    return False


class ActivationServer(QLocalServer):
    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.handler = None
        self.pending = False
        self.newConnection.connect(self.accept_activation)
        name = server_name(folder)
        # Only construct after acquiring app.lock, so stale sockets are safe to remove.
        QLocalServer.removeServer(name)
        if not self.listen(name):
            raise OSError(self.errorString())

    def accept_activation(self):
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            socket.close()
            socket.deleteLater()
            if self.handler is None:
                self.pending = True
            else:
                self.handler()

    def set_handler(self, handler):
        self.handler = handler
        if self.pending:
            self.pending = False
            QTimer.singleShot(0, handler)
