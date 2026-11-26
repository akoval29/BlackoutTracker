from PySide6.QtWidgets import QVBoxLayout, QLabel, QComboBox, QDialog, QDialogButtonBox
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, groups_for, valid_group


class SetupDialog(QDialog):
    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Налаштування BlackoutTracker')
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel('Оберіть свою чергу')
        title.setStyleSheet('font-size: 24px; font-weight: 600;')
        layout.addWidget(title)
        self.region_selector = QComboBox()
        for key, title in REGIONS.items():
            self.region_selector.addItem(title, key)
        layout.addWidget(self.region_selector)
        note = QLabel('Регіон і чергу можна змінити будь-коли в налаштуваннях.')
        note.setObjectName('muted')
        layout.addWidget(note)
        source_note = QLabel('Графік може змінюватися й не підтверджує фактичну наявність світла.')
        source_note.setWordWrap(True)
        source_note.setObjectName('muted')
        layout.addWidget(source_note)
        self.queue_selector = QComboBox()
        self.queue_selector.addItems(groups_for(DEFAULT_REGION))
        self.queue_selector.setCurrentText(group)
        self.queue_selector.setAccessibleName('Черга відключень')
        layout.addWidget(self.queue_selector)
        self.region_selector.currentIndexChanged.connect(self.update_groups)
        buttons = QDialogButtonBox()
        buttons.addButton('Зберегти', QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton('Скасувати', QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_groups(self, *_):
        group = self.queue_selector.currentText()
        region = self.region_selector.currentData()
        self.queue_selector.clear()
        self.queue_selector.addItems(groups_for(region))
        self.queue_selector.setCurrentText(valid_group(region, group))

