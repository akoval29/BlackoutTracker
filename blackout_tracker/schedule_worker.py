"""Qt worker for schedule requests outside the UI thread."""
from PySide6.QtCore import QThread, Signal
from blackout_tracker.regions import DEFAULT_REGION
from blackout_tracker.schedule import fetch_schedule


class ScheduleFetchWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, group, region=DEFAULT_REGION):
        super().__init__()
        self.group, self.region = group, region

    def run(self):
        try:
            self.ready.emit(fetch_schedule(self.group, self.region))
        except Exception as exc:
            self.failed.emit(str(exc))

