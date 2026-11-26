"""Deduplication and dismissal of upcoming outage notifications."""
from blackout_tracker.schedule import is_schedule_fresh, get_schedule_state


class AlertState:
    """One sound per scheduled outage per session; click dismissal survives polling."""
    def __init__(self):
        self.notified = {}
        self.dismissed = None
        self.key = None

    def dismiss(self):
        self.dismissed = self.key

    def evaluate(self, schedule, now, group, always=False):
        label, target, color = get_schedule_state(schedule, now)
        self.key = (group, target.isoformat() if target else None)
        self.notified = {k: v for k, v in self.notified.items() if v > now.timestamp() - 86400}
        imminent = (bool(schedule) and is_schedule_fresh(schedule, now)
                    and label == 'До відключення за графіком' and target is not None
                    and 0 < target.timestamp() - now.timestamp() <= 300)
        sound = imminent and self.key not in self.notified
        if sound:
            self.notified[self.key] = target.timestamp()
        visible = (always or imminent) and self.dismissed != self.key
        return visible, sound
