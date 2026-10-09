"""Recording schedules dialog (Tools menu).

Per camera: recording mode, motion sensitivity, per-weekday time windows.
Global: retention (days + disk cap) with a disk-usage readout.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QTime

from .resources import apply_icon
from .scheduler import RECORD_MODES, default_schedule, disk_usage_percent
from .storage import recordings_root

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

MODE_LABELS = {
    "always": "Always record",
    "scheduled": "Scheduled hours",
    "motion": "Motion only",
    "off": "Off",
}


class DayRow(QWidget):
    def __init__(self, day_index: int, windows: list | None = None):
        super().__init__()
        self.day_index = day_index
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.enable = QCheckBox(WEEKDAYS[day_index])
        self.start = QTimeEdit()
        self.start.setDisplayFormat("HH:mm")
        self.end = QTimeEdit()
        self.end.setDisplayFormat("HH:mm")
        start_s, end_s = "04:00", "22:00"
        if windows:
            start_s = windows[0][0] if len(windows[0]) > 0 else start_s
            end_s = windows[0][1] if len(windows[0]) > 1 else end_s
            self.enable.setChecked(True)
        else:
            self.enable.setChecked(False)
        self.start.setTime(QTime.fromString(start_s, "HH:mm"))
        self.end.setTime(QTime.fromString(end_s, "HH:mm"))
        self.enable.toggled.connect(self._sync_enabled)
        row.addWidget(self.enable)
        row.addWidget(QLabel("from"))
        row.addWidget(self.start)
        row.addWidget(QLabel("to"))
        row.addWidget(self.end)
        row.addStretch(1)
        self._sync_enabled(self.enable.isChecked())

    def _sync_enabled(self, on: bool) -> None:
        self.start.setEnabled(on)
        self.end.setEnabled(on)

    def value(self) -> list:
        if not self.enable.isChecked():
            return []
        return [[self.start.time().toString("HH:mm"),
                 self.end.time().toString("HH:mm")]]


class CameraSchedulePage(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        self._name = cfg.get("name", "Camera")
        layout = QVBoxLayout(self)

        top = QFormLayout()
        self.mode_combo = QComboBox()
        for mode in RECORD_MODES:
            self.mode_combo.addItem(MODE_LABELS[mode], mode)
        mode = cfg.get("record_mode", "scheduled")
        idx = self.mode_combo.findData(mode if mode in RECORD_MODES else "scheduled")
        self.mode_combo.setCurrentIndex(max(0, idx))
        top.addRow("Recording mode:", self.mode_combo)

        self.sens_combo = QComboBox()
        self.sens_combo.addItems(["low", "medium", "high"])
        sens = cfg.get("motion_sensitivity", "medium")
        self.sens_combo.setCurrentText(sens if sens in ("low", "medium", "high") else "medium")
        top.addRow("Motion sensitivity:", self.sens_combo)
        layout.addLayout(top)

        hours = QGroupBox("Recording hours (used by Scheduled hours mode)")
        days_layout = QVBoxLayout(hours)
        schedule = cfg.get("schedule") or {}
        self.day_rows = [DayRow(d, schedule.get(str(d))) for d in range(7)]
        for row in self.day_rows:
            days_layout.addWidget(row)
        layout.addWidget(hours)
        layout.addStretch(1)

        self.mode_combo.currentIndexChanged.connect(self._sync_mode)
        self._sync_mode()

    def _sync_mode(self) -> None:
        scheduled = self.mode_combo.currentData() == "scheduled"
        for row in self.day_rows:
            row.setEnabled(scheduled)

    def result(self) -> dict:
        return {
            "record_mode": self.mode_combo.currentData(),
            "motion_sensitivity": self.sens_combo.currentText(),
            "schedule": {str(r.day_index): r.value() for r in self.day_rows},
        }


class ScheduleDialog(QDialog):
    def __init__(self, cameras: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recording schedules")
        apply_icon(self)
        self.resize(640, 520)
        self._cameras = cameras

        root = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        self.cam_list = QListWidget()
        self.cam_list.setObjectName("CamList")
        self.cam_list.setMaximumWidth(200)
        for cfg in cameras:
            self.cam_list.addItem(cfg.get("name", "Camera"))
        self.cam_list.currentRowChanged.connect(self._show_page)
        split.addWidget(self.cam_list)

        self.pages: list[CameraSchedulePage] = []
        self.page_box = QVBoxLayout()
        page_wrap = QWidget()
        page_wrap.setLayout(self.page_box)
        split.addWidget(page_wrap)
        for cfg in cameras:
            page = CameraSchedulePage(cfg)
            page.setVisible(False)
            self.pages.append(page)
            self.page_box.addWidget(page)
        if cameras:
            self.cam_list.setCurrentRow(0)

        # -- retention (global) ------------------------------------------
        from .settings import load as load_settings

        settings = load_settings()
        reten = QGroupBox("Retention (all cameras)")
        form = QFormLayout(reten)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 90)
        self.days_spin.setValue(int(settings.get("retention_days", 7)))
        self.days_spin.setSuffix(" days")
        self.disk_spin = QSpinBox()
        self.disk_spin.setRange(50, 95)
        self.disk_spin.setValue(int(settings.get("max_disk_percent", 80)))
        self.disk_spin.setSuffix("% of disk")
        form.addRow("Keep recordings:", self.days_spin)
        form.addRow("Never exceed:", self.disk_spin)
        disk_row = QHBoxLayout()
        self.disk_label = QLabel()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_disk)
        disk_row.addWidget(self.disk_label, 1)
        disk_row.addWidget(refresh_btn)
        form.addRow("Disk usage:", disk_row)
        root.addWidget(reten)
        self._refresh_disk()

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

    def _show_page(self, row: int) -> None:
        for i, page in enumerate(self.pages):
            page.setVisible(i == row)

    def _refresh_disk(self) -> None:
        try:
            used = sum(f.stat().st_size for f in recordings_root().rglob("*.mp4"))
        except OSError:
            used = 0
        pct = disk_usage_percent()
        self.disk_label.setText(f"{used / 1048576:.0f} MB of clips, disk {pct:.0f}% full")

    def results(self) -> tuple[list[dict], dict]:
        """Returns (per-camera updates, retention settings)."""
        cams = []
        for cfg, page in zip(self._cameras, self.pages):
            updated = dict(cfg)
            updated.update(page.result())
            cams.append(updated)
        retention = {
            "retention_days": int(self.days_spin.value()),
            "max_disk_percent": int(self.disk_spin.value()),
        }
        return cams, retention
