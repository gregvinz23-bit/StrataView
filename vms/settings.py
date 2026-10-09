"""Application settings (settings.json) + Settings dialog."""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .resources import apply_icon
from . import storage


def settings_path() -> Path:
    return storage.BASE_DIR / "settings.json"


DEFAULTS = {
    "recordings_dir": "",
    "snapshots_dir": "",
    "segment_minutes": 10,
    "show_sidebar": True,
    "retention_days": 7,
    "max_disk_percent": 80,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in DEFAULTS if k in data})
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def save(cfg: dict) -> None:
    settings_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    storage.apply_directory_overrides(
        recordings=cfg.get("recordings_dir") or None,
        snapshots=cfg.get("snapshots_dir") or None,
    )


def apply_saved() -> dict:
    """Load settings and point storage at any custom folders. Returns cfg."""
    cfg = load()
    storage.apply_directory_overrides(
        recordings=cfg.get("recordings_dir") or None,
        snapshots=cfg.get("snapshots_dir") or None,
    )
    return cfg


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        apply_icon(self)
        self.setMinimumWidth(460)
        self._cfg = load()

        form = QFormLayout(self)

        self.rec_edit = QLineEdit(self._cfg["recordings_dir"])
        self.rec_edit.setPlaceholderText("Default: recordings folder next to the app")
        self.snap_edit = QLineEdit(self._cfg["snapshots_dir"])
        self.snap_edit.setPlaceholderText("Default: snapshots folder next to the app")

        rec_row = QHBoxLayout()
        rec_row.addWidget(self.rec_edit, 1)
        rec_browse = QPushButton("Browse…")
        rec_browse.clicked.connect(lambda: self._browse(self.rec_edit))
        rec_row.addWidget(rec_browse)

        snap_row = QHBoxLayout()
        snap_row.addWidget(self.snap_edit, 1)
        snap_browse = QPushButton("Browse…")
        snap_browse.clicked.connect(lambda: self._browse(self.snap_edit))
        snap_row.addWidget(snap_browse)

        self.segment_spin = QSpinBox()
        self.segment_spin.setRange(1, 120)
        self.segment_spin.setValue(int(self._cfg["segment_minutes"]))
        self.segment_spin.setSuffix(" min")

        self.sidebar_check = QCheckBox("Show camera list")
        self.sidebar_check.setChecked(bool(self._cfg["show_sidebar"]))

        form.addRow("Recordings folder:", rec_row)
        form.addRow("Snapshots folder:", snap_row)
        form.addRow("Recording segment:", self.segment_spin)
        form.addRow("", self.sidebar_check)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)

    def _browse(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", target.text())
        if path:
            target.setText(path)

    def _save_and_close(self) -> None:
        cfg = {
            "recordings_dir": self.rec_edit.text().strip(),
            "snapshots_dir": self.snap_edit.text().strip(),
            "segment_minutes": int(self.segment_spin.value()),
            "show_sidebar": bool(self.sidebar_check.isChecked()),
        }
        save(cfg)
        self.accept()

    def result_config(self) -> dict:
        return load()
