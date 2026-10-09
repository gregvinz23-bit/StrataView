"""PyQt6 VMS window: live grid, snapshots, recording, playback."""

from __future__ import annotations

import cv2
import numpy as np
from datetime import datetime
from PyQt6.QtCore import Qt, QSize, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QDesktopServices, QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDockWidget,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import events
from .backends import BaseSource, make_source
from .recorder import SegmentRecorder
from .resources import app_logo_pixmap, apply_icon
from .storage import clips_for, load_cameras, save_cameras, snapshot_path


def frame_to_pixmap(frame: np.ndarray, width: int, height: int) -> QPixmap:
    rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    h, w, _ = rgb.shape
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img).scaled(
        width, height, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class UpdateWorker(QThread):
    """Runs the update check off the GUI thread."""

    finished = pyqtSignal(dict)

    def run(self) -> None:  # noqa: N802
        from .updates import check_now

        try:
            self.finished.emit(check_now())
        except Exception as exc:  # never crash the thread silently
            self.finished.emit(
                {"bridge": ("error", f"check failed ({exc})"), "versions": []}
            )


class FullscreenView(QWidget):
    """Borderless fullscreen video for one camera.

    Reads frames from the same live source as the grid. Esc or
    double-click exits.
    """

    closed = pyqtSignal()

    def __init__(self, source, parent=None):
        super().__init__(
            None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.source = source
        self.setStyleSheet("background: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        strip = QHBoxLayout()
        strip.setContentsMargins(16, 10, 16, 10)
        name = QLabel(source.name)
        name.setObjectName("TileTitle")
        hint = QLabel("Double-click or press Esc to exit")
        hint.setObjectName("TileStatus")
        strip.addWidget(name)
        strip.addStretch(1)
        strip.addWidget(hint)
        layout.addLayout(strip)

        self.video = QLabel()
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.video, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._paint)
        self.timer.start(33)
        self.showFullScreen()

    def _paint(self) -> None:
        frame = self.source.latest()
        if frame is None:
            return
        size = self.video.size()
        if size.width() < 2 or size.height() < 2:
            return
        self.video.setPixmap(frame_to_pixmap(frame, size.width(), size.height()))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        self.closed.emit()
        super().closeEvent(event)


class CameraRow(QWidget):
    """One sidebar entry: status dot + name + REC badge."""
    def __init__(self, name: str):
        super().__init__()
        self.cam_name = name
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 5, 6, 5)
        row.setSpacing(6)
        self.dot = QLabel("●")
        self.dot.setObjectName("TileDot")
        self.name_label = QLabel(name)
        self.name_label.setObjectName("TileTitle")
        self.rec = QLabel("● REC")
        self.rec.setObjectName("TileRec")
        self.rec.setVisible(False)
        row.addWidget(self.dot)
        row.addWidget(self.name_label, 1)
        row.addWidget(self.rec)

    def update_state(self, live: bool, recording: bool) -> None:
        self.dot.setStyleSheet(f"color: {'#34d399' if live else '#f87171'};")
        self.rec.setVisible(recording)


class VideoTile(QWidget):
    """One grid cell: video + slim title strip. Click to select."""

    selected = pyqtSignal(str)
    retry_requested = pyqtSignal(str)
    zoom = pyqtSignal(str)

    # Statuses that resolve on their own — no Retry button for these.
    TRANSIENT = ("Connecting…", "Reconnecting…", "Preparing video…", "stopped", "")

    def __init__(self, name: str):
        super().__init__()
        self.cam_name = name
        self.setMinimumSize(240, 180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.bar = QWidget()
        self.bar.setObjectName("TileBar")
        strip = QHBoxLayout(self.bar)
        strip.setContentsMargins(8, 4, 8, 4)
        strip.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setObjectName("TileDot")
        self.title = QLabel(name)
        self.title.setObjectName("TileTitle")
        self.rec = QLabel("● REC")
        self.rec.setObjectName("TileRec")
        self.rec.setVisible(False)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setVisible(False)
        self.retry_btn.setToolTip("Try connecting again")
        self.retry_btn.clicked.connect(lambda: self.retry_requested.emit(self.cam_name))
        self.status = QLabel("")
        self.status.setObjectName("TileStatus")
        strip.addWidget(self.dot)
        strip.addWidget(self.title)
        strip.addWidget(self.status)
        strip.addStretch(1)
        strip.addWidget(self.retry_btn)
        strip.addWidget(self.rec)
        layout.addWidget(self.bar)

        self.video = QLabel("No signal")
        self.video.setObjectName("TileVideo")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(160, 120)
        layout.addWidget(self.video, 1)

        self._recording = False
        self._live = False
        self._update_dot()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.selected.emit(self.cam_name)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.zoom.emit(self.cam_name)
        super().mouseDoubleClickEvent(event)

    def set_selected(self, on: bool) -> None:
        if self.property("selected") == on:
            return
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_recording(self, on: bool) -> None:
        self._recording = on
        if not on:
            self.rec.setVisible(False)

    def blink_rec(self, visible: bool) -> None:
        if self._recording:
            self.rec.setVisible(visible)

    def set_frame(self, frame: np.ndarray | None, status: str) -> None:
        self._live = status == "live"
        self._update_dot()
        failed = not self._live and status not in self.TRANSIENT
        self.retry_btn.setVisible(failed)
        if frame is None:
            self.video.setPixmap(QPixmap())
            self.video.setText(status if status else "No signal")
            self.status.setText(status if not self._live else "")
        else:
            size = self.video.size()
            self.video.setPixmap(frame_to_pixmap(frame, size.width(), size.height()))
            self.status.setText("")
        if not self._recording:
            self.rec.setVisible(False)

    def _update_dot(self) -> None:
        color = "#34d399" if self._live else "#f87171"
        self.dot.setStyleSheet(f"color: {color};")


class AddCameraDialog(QDialog):
    """Vendor-style 'Add Device' dialog.

    Fields mirror the XMeye VMS popup: Device Name / Group / Login Type /
    CloudID-or-address / UserName / Password / Protocol.
    """

    LOGIN_TYPES = ["CloudID", "IP Address", "RTSP URL"]

    def __init__(self, parent=None, initial: dict | None = None,
                 groups: list[str] | None = None, allow_continue: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Add Device")
        apply_icon(self)
        self.result_config: dict | None = None
        self.wants_continue = False
        self._initial = initial or {}

        form = QFormLayout(self)

        self.name_edit = QLineEdit()

        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        ordered: list[str] = []
        for g in ["Default Group"] + list(groups or []):
            if g and g not in ordered:
                ordered.append(g)
        self.group_combo.addItems(ordered)

        self.login_combo = QComboBox()
        self.login_combo.addItems(self.LOGIN_TYPES)

        self.addr_label = QLabel("CloudID:")
        self.addr_edit = QLineEdit()
        self.user_edit = QLineEdit("admin")
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["General", "RTSP"])
        self.proto_combo.setEnabled(False)  # follows Login Type

        form.addRow("Device Name:", self.name_edit)
        form.addRow("Group:", self.group_combo)
        form.addRow("Login Type:", self.login_combo)
        form.addRow(self.addr_label, self.addr_edit)
        form.addRow("UserName:", self.user_edit)
        form.addRow("Password:", self.pass_edit)
        form.addRow("Protocol:", self.proto_combo)

        row = QHBoxLayout()
        self.save_cont_btn = QPushButton("Save And Continue")
        self.save_cont_btn.setVisible(allow_continue)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setObjectName("PrimaryButton")
        self.cancel_btn = QPushButton("Cancel")
        row.addWidget(self.save_cont_btn)
        row.addWidget(self.ok_btn)
        row.addWidget(self.cancel_btn)
        form.addRow(row)

        self.save_cont_btn.clicked.connect(lambda: self._finish(keep_open=True))
        self.ok_btn.clicked.connect(lambda: self._finish(keep_open=False))
        self.cancel_btn.clicked.connect(self.reject)
        self.login_combo.currentTextChanged.connect(self._on_login_changed)

        self._prefill()
        self._on_login_changed(self.login_combo.currentText())

    # -- setup ----------------------------------------------------------
    def _prefill(self) -> None:
        init = self._initial
        if not init:
            return
        self.name_edit.setText(init.get("name", ""))
        group = init.get("group", "Default Group")
        idx = self.group_combo.findText(group)
        if idx >= 0:
            self.group_combo.setCurrentIndex(idx)
        else:
            self.group_combo.setCurrentText(group)
        login = init.get("login_type")
        if not login:
            login = "RTSP URL" if init.get("type") == "rtsp" else "IP Address"
        idx = self.login_combo.findText(login)
        if idx >= 0:
            self.login_combo.setCurrentIndex(idx)
        if login == "RTSP URL":
            self.addr_edit.setText(init.get("url", ""))
        elif login == "CloudID":
            self.addr_edit.setText(init.get("cloud_id", init.get("host", "")))
        else:
            self.addr_edit.setText(init.get("host", ""))
        self.user_edit.setText(init.get("user", "admin"))
        self.pass_edit.setText(init.get("password", ""))

    def _on_login_changed(self, login: str) -> None:
        if login == "RTSP URL":
            self.addr_label.setText("RTSP URL:")
            self.addr_edit.setPlaceholderText("rtsp://user:pass@192.168.1.20:554/stream1")
            self.proto_combo.setCurrentText("RTSP")
        elif login == "CloudID":
            self.addr_label.setText("CloudID:")
            self.addr_edit.setPlaceholderText("e.g. ab12cd34ef567890")
            self.proto_combo.setCurrentText("General")
        else:
            self.addr_label.setText("IP Address:")
            self.addr_edit.setPlaceholderText("e.g. 10.20.30.121")
            self.proto_combo.setCurrentText("General")

    # -- result ---------------------------------------------------------
    def _collect(self) -> dict | None:
        name = self.name_edit.text().strip()
        addr = self.addr_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Add Device", "Please enter a Device Name.")
            return None
        if not addr:
            QMessageBox.warning(self, "Add Device", "Please enter the device address.")
            return None
        login = self.login_combo.currentText()
        group = self.group_combo.currentText().strip() or "Default Group"
        if login == "RTSP URL":
            cfg = {"name": name, "type": "rtsp", "url": addr}
        else:
            cfg = {
                "name": name,
                "type": "dvrip",
                "user": self.user_edit.text().strip() or "admin",
                "password": self.pass_edit.text(),
                "port": int(self._initial.get("port", 34567)),
                "channel": int(self._initial.get("channel", 0)),
            }
            if login == "CloudID":
                cfg["cloud_id"] = addr
                cfg["host"] = addr  # tried as-is; will show an error tile if unreachable
            else:
                cfg["host"] = addr
        cfg["group"] = group
        cfg["login_type"] = login
        cfg["enabled"] = True
        return cfg

    def _finish(self, keep_open: bool) -> None:
        cfg = self._collect()
        if cfg is None:
            return
        self.result_config = cfg
        self.wants_continue = keep_open
        self.accept()

    def reset_for_next(self) -> None:
        """Clear per-device fields so another device can be entered."""
        self.result_config = None
        self.wants_continue = False
        self.name_edit.clear()
        self.addr_edit.clear()
        self.pass_edit.clear()
        self.name_edit.setFocus()


class PlaybackDialog(QDialog):
    """Browse recorded clips per camera and play them back."""

    def __init__(self, camera_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playback")
        apply_icon(self)
        self.resize(820, 560)
        self._cap: cv2.VideoCapture | None = None
        self._playing = False
        self._total = 0

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(camera_names)
        self.clip_list = QListWidget()
        left.addWidget(self.cam_combo)
        left.addWidget(self.clip_list, 1)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        self.video = QLabel("Select a recording to play")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setStyleSheet("background:black; color:#888;")
        self.video.setMinimumSize(480, 360)
        right.addWidget(self.video, 1)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("PrimaryButton")
        self.pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.pos_label = QLabel("0 / 0")
        controls.addWidget(self.play_btn)
        controls.addWidget(self.pos_slider, 1)
        controls.addWidget(self.pos_label)
        right.addLayout(controls)
        root.addLayout(right, 2)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._fps = 10.0

        self.cam_combo.currentTextChanged.connect(self._refresh_clips)
        self.clip_list.itemSelectionChanged.connect(self._open_selected)
        self.play_btn.clicked.connect(self._toggle_play)
        self.pos_slider.sliderReleased.connect(self._seek)
        self._refresh_clips(self.cam_combo.currentText())

    def _refresh_clips(self, name: str) -> None:
        self._stop_play()
        self.clip_list.clear()
        for clip in clips_for(name):
            self.clip_list.addItem(clip.name)
        self.clip_list.setProperty("camera", name)

    def _current_path(self):
        name = self.clip_list.property("camera") or self.cam_combo.currentText()
        item = self.clip_list.currentItem()
        if not item:
            return None
        from pathlib import Path

        matches = [c for c in clips_for(name) if c.name == item.text()]
        return matches[0] if matches else None

    def _open_selected(self) -> bool:
        path = self._current_path()
        if path is None:
            return False
        self._stop_play()
        self._cap = cv2.VideoCapture(str(path))
        self._total = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 10.0
        self.timer.setInterval(max(20, int(1000 / self._fps)))
        self.pos_slider.setRange(0, max(0, self._total - 1))
        self._toggle_play(force=True)
        return True

    def open_at(self, camera: str, moment) -> bool:
        """Open the clip containing `moment` and seek to it. For event jumps."""
        from datetime import datetime

        idx = self.cam_combo.findText(camera)
        if idx < 0:
            return False
        self.cam_combo.setCurrentIndex(idx)
        if not isinstance(moment, datetime):
            moment = datetime.now()
        target = None
        for clip in clips_for(camera):
            try:
                start = datetime.strptime(clip.stem[:15], "%Y%m%d_%H%M%S")
            except ValueError:
                continue
            if start <= moment:
                target = (clip, start)
            else:
                break
        if target is None:
            return False
        clip, start = target
        for i in range(self.clip_list.count()):
            if self.clip_list.item(i).text() == clip.name:
                self.clip_list.setCurrentRow(i)
                break
        if not self._open_selected():
            return False
        offset = max(0.0, (moment - start).total_seconds())
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, int(offset * (self._fps or 10.0)))
        return True

    def _toggle_play(self, force: bool = False) -> None:
        if self._cap is None:
            return
        self._playing = True if force else not self._playing
        self.play_btn.setText("Pause" if self._playing else "Play")
        if self._playing:
            self.timer.start()
        else:
            self.timer.stop()

    def _stop_play(self) -> None:
        self._playing = False
        self.timer.stop()
        self.play_btn.setText("Play")
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _tick(self) -> None:
        if self._cap is None or not self._playing:
            return
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._stop_play()
            return
        pos = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        size = self.video.size()
        self.video.setPixmap(frame_to_pixmap(frame, size.width(), size.height()))
        self.pos_slider.blockSignals(True)
        self.pos_slider.setValue(pos)
        self.pos_slider.blockSignals(False)
        self.pos_label.setText(f"{pos} / {self._total}")

    def _seek(self) -> None:
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, self.pos_slider.value())

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_play()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StrataView")
        apply_icon(self)
        self.resize(1100, 700)

        self.sources: dict[str, BaseSource] = {}
        self.recorders: dict[str, SegmentRecorder] = {}
        self.tiles: dict[str, VideoTile] = {}
        self.selected: str | None = None
        self.grid_cols = 2
        self._fs_view: FullscreenView | None = None
        self.detectors: dict = {}
        self.trackers: dict = {}
        self._blink_on = False
        self._tick_count = 0
        self._last_status: dict[str, str] = {}
        self._motion_index: dict[tuple, dict] = {}
        # -- toolbar ----------------------------------------------------
        toolbar = QToolBar("Main")
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["1", "2 × 2", "3 × 3"])
        self.layout_combo.setCurrentIndex(1)
        self.layout_combo.setToolTip("Grid layout")
        self.layout_combo.currentIndexChanged.connect(self._change_layout)
        toolbar.addWidget(QLabel("Grid: "))
        toolbar.addWidget(self.layout_combo)
        toolbar.addSeparator()

        from . import icons as app_icons

        # Device management lives in the File menu — toolbar keeps
        # only the everyday actions: Snapshot, Record, Playback.
        add_act = QAction(app_icons.add_device(), "Add Device", self)
        add_act.setToolTip("Add a camera (Ctrl+N)")
        add_act.setShortcut("Ctrl+N")
        add_act.triggered.connect(self._add_camera)
        self.add_act = add_act

        self.edit_act = QAction(app_icons.edit(), "Edit", self)
        self.edit_act.setToolTip("Edit the selected camera")
        self.edit_act.triggered.connect(self._edit_selected)

        self.remove_act = QAction(app_icons.remove(), "Remove", self)
        self.remove_act.setToolTip("Remove the selected camera")
        self.remove_act.triggered.connect(self._remove_selected)

        self.snap_act = QAction(app_icons.snapshot(), "Snapshot", self)
        self.snap_act.setToolTip("Save a still image from the selected camera (Ctrl+S)")
        self.snap_act.setShortcut("Ctrl+S")
        self.snap_act.triggered.connect(self._snapshot_selected)
        toolbar.addAction(self.snap_act)

        self.rec_act = QAction(app_icons.record(), "Record", self)
        self.rec_act.setToolTip("Start or stop recording the selected camera (Ctrl+R)")
        self.rec_act.setShortcut("Ctrl+R")
        self.rec_act.setCheckable(True)
        self.rec_act.triggered.connect(self._toggle_record)
        toolbar.addAction(self.rec_act)

        toolbar.addSeparator()
        play_act = QAction(app_icons.playback(), "Playback", self)
        play_act.setToolTip("Browse and play recorded clips (Ctrl+P)")
        play_act.setShortcut("Ctrl+P")
        play_act.triggered.connect(self._open_playback)
        toolbar.addAction(play_act)
        self.play_act = play_act

        about_act = QAction(app_icons.about(), "About", self)
        about_act.setToolTip("About StrataView")
        about_act.triggered.connect(self._open_about)

        # -- menu bar -----------------------------------------------------
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(add_act)
        file_menu.addAction(self.edit_act)
        file_menu.addAction(self.remove_act)
        file_menu.addSeparator()
        quit_act = QAction("Exit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        view_menu = menubar.addMenu("View")
        self.grid_group = QActionGroup(self)
        self.grid_group.setExclusive(True)
        for i, label in enumerate(["Single camera", "2 × 2 grid", "3 × 3 grid"]):
            act = QAction(label, self, checkable=True)
            act.setChecked(i == 1)
            act.triggered.connect(
                lambda _checked=False, idx=i: self.layout_combo.setCurrentIndex(idx)
            )
            self.grid_group.addAction(act)
            view_menu.addAction(act)
        view_menu.addSeparator()
        self.sidebar_act = QAction("Camera list", self, checkable=True)
        self.sidebar_act.setChecked(True)
        self.sidebar_act.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(self.sidebar_act)
        self.logdock_act = QAction("Event log", self, checkable=True)
        self.logdock_act.setChecked(True)
        self.logdock_act.triggered.connect(self._toggle_logdock)
        view_menu.addAction(self.logdock_act)
        view_menu.addSeparator()
        self.fullscreen_act = QAction("Fullscreen", self, checkable=True)
        self.fullscreen_act.setShortcut("F11")
        self.fullscreen_act.setToolTip("Toggle fullscreen (F11)")
        self.fullscreen_act.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(self.fullscreen_act)

        tools_menu = menubar.addMenu("Tools")
        rec_folder_act = QAction(app_icons.folder(), "Open recordings folder", self)
        rec_folder_act.triggered.connect(self._open_recordings_folder)
        tools_menu.addAction(rec_folder_act)
        snap_folder_act = QAction(app_icons.folder(), "Open snapshots folder", self)
        snap_folder_act.triggered.connect(self._open_snapshots_folder)
        tools_menu.addAction(snap_folder_act)
        tools_menu.addSeparator()
        sched_act = QAction("Recording schedules", self)
        sched_act.triggered.connect(self._open_schedules)
        tools_menu.addAction(sched_act)
        health_act = QAction("Camera health", self)
        health_act.triggered.connect(self._open_health)
        tools_menu.addAction(health_act)
        tools_menu.addSeparator()
        settings_act = QAction(app_icons.settings(), "Settings", self)
        settings_act.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_act)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(about_act)

        stretch = QWidget()
        stretch.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(stretch)
        brand = QWidget()
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(0, 0, 4, 0)
        brand_row.setSpacing(6)
        brand_logo = QLabel()
        brand_logo.setPixmap(app_logo_pixmap(22))
        brand_text = QLabel("StrataView")
        brand_text.setObjectName("BrandLabel")
        brand_row.addWidget(brand_logo)
        brand_row.addWidget(brand_text)
        toolbar.addWidget(brand)

        # -- layout: sidebar + grid ------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        main_row = QHBoxLayout(central)
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)

        self.side = QFrame()
        self.side.setObjectName("SidePanel")
        self.side.setFixedWidth(230)
        side_layout = QVBoxLayout(self.side)
        side_layout.setContentsMargins(8, 8, 8, 8)
        side_layout.setSpacing(6)
        self.side_header = QLabel("Cameras")
        self.side_header.setObjectName("SideHeader")
        side_layout.addWidget(self.side_header)
        self.cam_list = QListWidget()
        self.cam_list.setObjectName("CamList")
        self.cam_list.itemClicked.connect(self._on_list_clicked)
        side_layout.addWidget(self.cam_list, 1)

        grid_wrap = QWidget()
        self.grid = QGridLayout(grid_wrap)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setSpacing(4)
        main_row.addWidget(self.side)
        main_row.addWidget(grid_wrap, 1)

        self.setStatusBar(QStatusBar())

        # -- event log dock -------------------------------------------------
        from . import events

        self.log_dock = QDockWidget("Event log", self)
        self.log_dock.setObjectName("LogDock")
        log_wrap = QWidget()
        log_layout = QVBoxLayout(log_wrap)
        log_layout.setContentsMargins(6, 6, 6, 6)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self.log_filter = QComboBox()
        self.log_filter.addItems(
            ["All", "Motion", "Recording", "Camera", "App", "Snapshot", "View"]
        )
        self.log_filter.currentTextChanged.connect(self._refill_log_view)
        filter_row.addWidget(self.log_filter)
        filter_row.addStretch(1)
        log_layout.addLayout(filter_row)
        self.log_view = QListWidget()
        self.log_view.setObjectName("LogView")
        self.log_view.itemDoubleClicked.connect(self._on_log_doubleclick)
        log_layout.addWidget(self.log_view, 1)
        log_buttons = QHBoxLayout()
        export_btn = QPushButton("Export…")
        export_btn.setToolTip("Save the event log to a text file")
        export_btn.clicked.connect(self._export_log)
        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Clear the event log view")
        clear_btn.clicked.connect(self._clear_log)
        log_buttons.addStretch(1)
        log_buttons.addWidget(export_btn)
        log_buttons.addWidget(clear_btn)
        log_layout.addLayout(log_buttons)
        self.log_dock.setWidget(log_wrap)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self._log_view_index = 0

        self._load_all()

        self.refresh = QTimer(self)
        self.refresh.timeout.connect(self._update_tiles)
        self.refresh.start(100)
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_log_view)
        self.log_timer.start(1000)

        # Recording scheduler, motion detectors, health trackers.
        # (self.detectors / self.trackers are created with the other state
        # above because _load_all() already needs them.)
        from .motion import MotionDetector
        from .scheduler import Scheduler

        self.scheduler = Scheduler(
            get_sources=lambda: list(self.sources),
            get_config=self._config_for,
            is_motion_active=self._motion_active,
            apply_state=self._apply_recording,
            parent=self,
        )
        self.watchdog = QTimer(self)
        self.watchdog.timeout.connect(self._watchdog_tick)
        self.watchdog.start(15_000)

        events.log("app", "StrataView started.")
        self.scheduler.evaluate()
        QTimer.singleShot(10_000, self.scheduler.sweep)

        from .settings import load as load_settings

        show_sidebar = bool(load_settings().get("show_sidebar", True))
        self.side.setVisible(show_sidebar)
        self.sidebar_act.setChecked(show_sidebar)

    # -- setup ----------------------------------------------------------
    def _load_all(self) -> None:
        for cfg in load_cameras():
            if cfg.get("enabled", True):
                self._start_source(cfg)
        # Fit the grid to the camera count: 1 -> single, up to 4 -> 2x2.
        count = len(self.sources)
        self._apply_layout_index(0 if count <= 1 else (1 if count <= 4 else 2))
        if self.sources:
            self._select(next(iter(self.sources)))
            self.statusBar().showMessage(
                f"Ready — {len(self.sources)} camera(s) connected."
            )
        else:
            self.statusBar().showMessage(
                "No cameras yet. Use Add Device to add your first camera."
            )

    def maybe_first_run(self) -> None:
        """Run the setup wizard when no cameras are configured."""
        if self.sources:
            return
        from .wizard import FirstRunWizard

        wiz = FirstRunWizard(self, groups=self._known_groups())
        if wiz.exec() != QDialog.DialogCode.Accepted:
            return
        cfg = wiz.camera_config()
        if cfg is None:
            return
        existing = [c.get("name", "") for c in load_cameras()]
        if FirstRunWizard.check_duplicate(self, cfg["name"], existing):
            return
        self._save_config(cfg)
        self._start_source(cfg)
        self._rebuild_grid()
        self._select(cfg["name"])
        self.statusBar().showMessage(
            f"Camera '{cfg['name']}' added. Connecting — this can take up to 30 seconds."
        )

    def _start_source(self, cfg: dict) -> None:
        from . import events

        name = cfg.get("name", "Camera")
        if name in self.sources:
            return
        try:
            src = make_source(cfg)
        except Exception as exc:
            self.statusBar().showMessage(f"{name}: {exc}")
            events.log("camera", f"Could not start '{name}': {exc}")
            return
        src.start()
        self.sources[name] = src
        events.log("camera", f"Connecting to {name}…")
        self._ensure_helpers(name, cfg)

    def _ensure_helpers(self, name: str, cfg: dict) -> None:
        """Create/refresh the motion detector + health tracker for a camera."""
        from .health import HealthTracker
        from .motion import MotionDetector

        src = self.sources.get(name)
        if src is None:
            return
        if name not in self.trackers:
            self.trackers[name] = HealthTracker()
        det = self.detectors.get(name)
        want_motion = cfg.get("record_mode", "scheduled") == "motion"
        if want_motion and det is None:
            import functools

            det = MotionDetector(
                src,
                sensitivity=cfg.get("motion_sensitivity", "medium"),
                on_event=functools.partial(self._on_motion, name),
            )
            det.start()
            self.detectors[name] = det
        elif want_motion and det is not None:
            det.set_sensitivity(cfg.get("motion_sensitivity", "medium"))
        elif not want_motion and det is not None:
            det.stop()
            del self.detectors[name]

    def _drop_helpers(self, name: str) -> None:
        det = self.detectors.pop(name, None)
        if det is not None:
            det.stop()
        self.trackers.pop(name, None)

    def _config_for(self, name: str) -> dict:
        for cfg in load_cameras():
            if cfg.get("name") == name:
                return cfg
        return {"name": name, "record_mode": "scheduled"}

    def _motion_active(self, name: str) -> bool:
        det = self.detectors.get(name)
        return bool(det and det.active)

    def _apply_recording(self, name: str, want: bool, auto: bool = False) -> None:
        src = self.sources.get(name)
        if src is None:
            return
        rec = self.recorders.get(name)
        running = bool(rec and rec.running)
        if want and not running:
            from .settings import load as load_settings

            segment = int(load_settings().get("segment_minutes", 10)) * 60
            rec = SegmentRecorder(src, segment_seconds=segment)
            self.recorders[name] = rec
            rec.start()
            self.statusBar().showMessage(f"Recording started: {name}")
            events.log("recording", f"Recording started: {name}")
        elif not want and running and rec is not None:
            rec.stop()
            clip = rec.current_file.name if rec.current_file else "clip"
            events.log("recording", f"Recording stopped: {name} ({clip})")
            self.statusBar().showMessage(f"Recording stopped: {name}")

    def _on_motion(self, name: str) -> None:
        from . import events

        src = self.sources.get(name)
        frame = src.latest() if src else None
        now = datetime.now()
        if frame is None:
            message = f"Motion detected: {name}"
        else:
            path = snapshot_path(name, prefix="motion_")
            try:
                cv2.imwrite(str(path), frame)
                message = f"Motion detected: {name} ({path.name})"
            except Exception:
                message = f"Motion detected: {name}"
        stamp = events.log("motion", message)
        self._motion_index[(stamp, "motion", message)] = {"camera": name, "at": now}

    def _watchdog_tick(self) -> None:
        from . import events
        from .health import check_source

        for name, src in list(self.sources.items()):
            tracker = self.trackers.get(name)
            if tracker is None:
                continue
            action = check_source(name, src, tracker)
            if action == "restart":
                events.log("camera", f"Stream stalled. Restarting {name}…")
                self.statusBar().showMessage(f"Connection lost. Restarting {name}…")
                src.stop()
                src.start()
            elif action == "unstable":
                events.log(
                    "camera",
                    f"{name} is unstable. Pausing retries for 15 minutes. "
                    "Use Retry to reconnect sooner.",
                )
                self.statusBar().showMessage(
                    f"{name} is unstable — retrying later. Use Retry to reconnect sooner."
                )
                src.stop()

    # -- grid -----------------------------------------------------------
    def _apply_layout_index(self, index: int) -> None:
        self.grid_cols = (1, 2, 3)[index]
        for i, act in enumerate(self.grid_group.actions()):
            act.blockSignals(True)
            act.setChecked(i == index)
            act.blockSignals(False)
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(index)
        self.layout_combo.blockSignals(False)
        self._rebuild_grid()

    def _change_layout(self, index: int) -> None:
        self._apply_layout_index(index)

    def _rebuild_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.tiles.clear()
        names = list(self.sources)[: self.grid_cols * self.grid_cols]
        if not names:
            hint = QLabel("No cameras yet — click  Add Device  to add your first camera.")
            hint.setObjectName("HintLabel")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(hint, 0, 0)
            self._select(None)
            self._rebuild_sidebar()
            return
        for i, name in enumerate(names):
            tile = VideoTile(name)
            tile.selected.connect(self._select)
            tile.retry_requested.connect(self._retry_source)
            tile.zoom.connect(self._open_fullscreen)
            tile.set_selected(name == self.selected)
            if name in self.recorders and self.recorders[name].running:
                tile.set_recording(True)
            self.tiles[name] = tile
            self.grid.addWidget(tile, i // self.grid_cols, i % self.grid_cols)
        if self.selected not in self.tiles:
            self._select(names[0] if names else None)
        self._rebuild_sidebar()

    def _open_fullscreen(self, name: str) -> None:
        from . import events

        if self._fs_view is not None:
            return
        src = self.sources.get(name)
        if src is None:
            return
        frame = src.latest()
        if frame is None:
            self.statusBar().showMessage(
                f"{name} has no video yet. Wait for the camera to connect."
            )
            return
        self._select(name)
        self._fs_view = FullscreenView(src)
        self._fs_view.closed.connect(self._on_fullscreen_closed)
        events.log("view", f"Fullscreen view opened: {name}.")

    def _on_fullscreen_closed(self) -> None:
        self._fs_view = None

    # -- sidebar --------------------------------------------------------
    def _rebuild_sidebar(self) -> None:
        self.cam_list.blockSignals(True)
        self.cam_list.clear()
        self._rows: dict[str, CameraRow] = {}
        self._row_items: dict = {}
        names = list(self.sources)
        self.side_header.setText(f"Cameras ({len(names)})")
        for name in names:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setSizeHint(QSize(200, 34))
            row = CameraRow(name)
            self._rows[name] = row
            self._row_items[name] = item
            self.cam_list.addItem(item)
            self.cam_list.setItemWidget(item, row)
        self.cam_list.blockSignals(False)
        self._sync_sidebar_selection()

    def _sync_sidebar_selection(self) -> None:
        self.cam_list.blockSignals(True)
        for i in range(self.cam_list.count()):
            item = self.cam_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.selected:
                self.cam_list.setCurrentRow(i)
                break
        else:
            self.cam_list.clearSelection()
        self.cam_list.blockSignals(False)

    def _on_list_clicked(self, item: QListWidgetItem) -> None:
        self._select(item.data(Qt.ItemDataRole.UserRole))

    def _update_tiles(self) -> None:
        from . import events
        from .health import HealthTracker

        self._tick_count += 1
        if self._tick_count % 5 == 0:  # ~1 Hz blink for REC badges
            self._blink_on = not self._blink_on
        for name, tile in self.tiles.items():
            src = self.sources.get(name)
            if src is None:
                continue
            status = src.status
            tracker = self.trackers.get(name)
            if tracker is None:
                tracker = HealthTracker()
                self.trackers[name] = tracker
            tracker.observe(status, getattr(src, "frame_count", 0))
            if status != self._last_status.get(name):
                self._last_status[name] = status
                if status == "live":
                    events.log("camera", f"'{name}' is live.")
                elif status not in ("Connecting…", "Reconnecting…", "Preparing video…"):
                    events.log("camera", f"'{name}': {status}")
            tile.set_frame(src.latest(), status)
            tile.blink_rec(self._blink_on)
            rec = self.recorders.get(name)
            tile.set_recording(bool(rec and rec.running))
        for name, row in getattr(self, "_rows", {}).items():
            src = self.sources.get(name)
            rec = self.recorders.get(name)
            row.update_state(
                live=(src.status == "live") if src else False,
                recording=bool(rec and rec.running),
            )
        for name, item in getattr(self, "_row_items", {}).items():
            tracker = self.trackers.get(name)
            src = self.sources.get(name)
            if tracker and src:
                item.setToolTip(
                    f"{name}\nStatus: {src.status}\n"
                    f"Uptime: {HealthTracker.format_uptime(tracker.live_seconds)}\n"
                    f"Reconnects: {tracker.reconnects}\n"
                    f"Rate: {tracker.fps:.0f} fps\n"
                    f"Last error: {tracker.last_error or 'none'}"
                )
        if self.selected and self._tick_count % 5 == 0:
            rec = self.recorders.get(self.selected)
            on = bool(rec and rec.running)
            self.rec_act.blockSignals(True)
            self.rec_act.setChecked(on)
            self.rec_act.blockSignals(False)

    def _select(self, name: str | None) -> None:
        self.selected = name
        for n, tile in self.tiles.items():
            tile.set_selected(n == name)
        self._sync_sidebar_selection()
        rec_on = (
            name in self.recorders and self.recorders[name].running
        ) if name else False
        self.rec_act.blockSignals(True)
        self.rec_act.setChecked(rec_on)
        self.rec_act.blockSignals(False)
        if name:
            self.statusBar().showMessage(f"Selected: {name}")

    # -- actions --------------------------------------------------------
    def _known_groups(self) -> list[str]:
        groups: list[str] = []
        for c in load_cameras():
            g = c.get("group", "Default Group")
            if g and g not in groups:
                groups.append(g)
        return groups or ["Default Group"]

    def _save_config(self, cfg: dict) -> None:
        from .scheduler import with_defaults

        with_defaults(cfg)
        cameras = [c for c in load_cameras() if c.get("name") != cfg["name"]]
        cameras.append(cfg)
        save_cameras(cameras)

    def _add_camera(self) -> None:
        from . import events

        dlg = AddCameraDialog(self, groups=self._known_groups())
        while dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.result_config
            if cfg is None:
                break
            if cfg["name"] in self.sources:
                QMessageBox.warning(self, "Add Device",
                                    f"A camera named '{cfg['name']}' already exists.")
                dlg.result_config = None
                dlg.wants_continue = False
                continue  # re-open with values intact so they can fix the name
            self._save_config(cfg)
            self._start_source(cfg)
            self._rebuild_grid()
            self._select(cfg["name"])
            events.log("camera", f"Camera added: {cfg['name']}")
            if not dlg.wants_continue:
                break
            dlg.reset_for_next()

    def _edit_selected(self) -> None:
        from . import events

        name = self.selected
        if not name:
            return
        current = next((c for c in load_cameras() if c.get("name") == name), None)
        if current is None:
            return
        dlg = AddCameraDialog(self, initial=current,
                              groups=self._known_groups(), allow_continue=False)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.result_config is None:
            return
        from .scheduler import with_defaults

        cfg = with_defaults(dlg.result_config)
        old_name = name
        if cfg["name"] != old_name and cfg["name"] in self.sources:
            QMessageBox.warning(self, "Edit Device",
                                f"A camera named '{cfg['name']}' already exists.")
            return
        # Swap the running source (recording files already on disk are kept).
        if old_name in self.recorders:
            self.recorders[old_name].stop()
            del self.recorders[old_name]
        self._drop_helpers(old_name)
        if old_name in self.sources:
            self.sources[old_name].stop()
            del self.sources[old_name]
        cameras = [c for c in load_cameras() if c.get("name") != old_name]
        cameras.append(cfg)
        save_cameras(cameras)
        self._start_source(cfg)
        self._rebuild_grid()
        self._select(cfg["name"])
        events.log("camera", f"Camera updated: {old_name} -> {cfg['name']}")

    def _remove_selected(self) -> None:
        from . import events

        name = self.selected
        if not name:
            return
        if QMessageBox.question(
            self, "Remove camera",
            f"Remove '{name}'? Recordings already saved will be kept.",
        ) != QMessageBox.StandardButton.Yes:
            return
        if name in self.recorders:
            self.recorders[name].stop()
            del self.recorders[name]
        self._drop_helpers(name)
        if name in self.sources:
            self.sources[name].stop()
            del self.sources[name]
        save_cameras([c for c in load_cameras() if c.get("name") != name])
        self._rebuild_grid()
        events.log("camera", f"Camera removed: {name}")

    def _snapshot_selected(self) -> None:
        from . import events

        name = self.selected
        src = self.sources.get(name) if name else None
        if src is None:
            return
        frame = src.latest()
        if frame is None:
            QMessageBox.information(
                self, "Snapshot",
                "No video frame available yet. Wait for the camera to connect.",
            )
            return
        path = snapshot_path(name)
        cv2.imwrite(str(path), frame)
        self.statusBar().showMessage(f"Snapshot saved: {path.name}")
        events.log("snapshot", f"Snapshot saved: {path.name}")

    def _toggle_record(self, on: bool) -> None:
        from . import events

        name = self.selected
        src = self.sources.get(name) if name else None
        if src is None:
            self.rec_act.blockSignals(True)
            self.rec_act.setChecked(False)
            self.rec_act.blockSignals(False)
            return
        cameras = load_cameras()
        for cfg in cameras:
            if cfg.get("name") == name:
                cfg["record_mode"] = "always" if on else "off"
                break
        save_cameras(cameras)
        self._apply_recording(name, on)
        if on:
            events.log("recording", f"Recording set to Always: {name}")
        else:
            events.log("recording", f"Recording turned off: {name}")

    def _toggle_sidebar(self, on: bool) -> None:
        self.side.setVisible(on)

    def _toggle_fullscreen(self, on: bool) -> None:
        if on:
            self.showFullScreen()
            self.statusBar().showMessage("Fullscreen — press F11 to exit.")
        else:
            self.showNormal()

    def _toggle_logdock(self, on: bool) -> None:
        self.log_dock.setVisible(on)

    # -- event log ------------------------------------------------------
    def _log_matches_filter(self, category: str) -> bool:
        wanted = self.log_filter.currentText()
        return wanted == "All" or category == wanted.lower()

    def _refill_log_view(self) -> None:
        from . import events

        self.log_view.clear()
        self._log_view_index = 0
        self._refresh_log_view()

    def _refresh_log_view(self) -> None:
        from . import events

        entries = events.get_all()
        for stamp, category, message in entries[self._log_view_index :]:
            if not self._log_matches_filter(category):
                continue
            item = QListWidgetItem(events.format_entry(stamp, category, message))
            key = (stamp, category, message)
            if key in self._motion_index:
                item.setData(Qt.ItemDataRole.UserRole, self._motion_index[key])
            self.log_view.addItem(item)
            self.log_view.scrollToBottom()
        self._log_view_index = len(entries)

    def _on_log_doubleclick(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or "camera" not in data:
            return
        dlg = PlaybackDialog(list(self.sources), self)
        if dlg.open_at(data["camera"], data.get("at")):
            dlg.exec()

    def _export_log(self) -> None:
        from datetime import datetime

        from . import events

        default = f"strataview-log-{datetime.now():%Y%m%d}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export event log", default, "Text files (*.txt)"
        )
        if not path:
            return
        try:
            events.export_to(path)
            self.statusBar().showMessage("Event log exported.")
            events.log("app", "Event log exported.")
        except OSError as exc:
            QMessageBox.warning(
                self, "Export event log",
                f"Could not write the file: {exc}",
            )

    def _clear_log(self) -> None:
        from . import events

        events.clear()
        self.log_view.clear()
        self._log_view_index = 0

    def _retry_source(self, name: str) -> None:
        from . import events

        src = self.sources.get(name)
        if src is None:
            return
        events.log("camera", f"Manual reconnect requested for '{name}'.")
        self.statusBar().showMessage(f"Reconnecting to {name}…")
        src.stop()
        src.start()

    def _open_recordings_folder(self) -> None:
        from .storage import recordings_root

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(recordings_root())))

    def _open_snapshots_folder(self) -> None:
        from .storage import snapshots_root

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(snapshots_root())))

    def _open_settings(self) -> None:
        from . import events
        from .settings import SettingsDialog

        dlg = SettingsDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cfg = dlg.result_config()
        show = bool(cfg.get("show_sidebar", True))
        self.side.setVisible(show)
        self.sidebar_act.blockSignals(True)
        self.sidebar_act.setChecked(show)
        self.sidebar_act.blockSignals(False)
        self.statusBar().showMessage("Settings saved.")
        events.log("app", "Settings saved.")

    def _open_schedules(self) -> None:
        from . import events
        from .schedule_dialog import ScheduleDialog

        cameras = load_cameras()
        dlg = ScheduleDialog(cameras, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated, retention = dlg.results()
        save_cameras(updated)
        from .settings import load as load_settings
        from .settings import save as save_settings

        settings = load_settings()
        settings.update(retention)
        save_settings(settings)
        # Refresh detectors (mode/sensitivity may have changed).
        for cfg in updated:
            name = cfg.get("name", "")
            if name in self.sources:
                self._ensure_helpers(name, cfg)
        self.scheduler.evaluate()
        self.statusBar().showMessage("Recording schedules saved.")
        events.log("app", "Recording schedules saved.")

    def _open_health(self) -> None:
        from .health import HealthDialog, HealthTracker

        def rows():
            out = []
            for name, src in self.sources.items():
                tracker = self.trackers.get(name)
                if tracker is None:
                    tracker = HealthTracker()
                    self.trackers[name] = tracker
                out.append((
                    name,
                    src.status,
                    HealthTracker.format_uptime(tracker.live_seconds),
                    tracker.reconnects,
                    f"{tracker.fps:.0f} fps",
                    tracker.last_error or "—",
                ))
            return out

        HealthDialog(rows, self).exec()

    def _open_playback(self) -> None:
        if not self.sources:
            QMessageBox.information(
                self, "Playback", "There are no cameras to play back from."
            )
            return
        PlaybackDialog(list(self.sources), self).exec()

    def _open_about(self) -> None:
        from vms import __app_name__, __version__

        dlg = QDialog(self)
        dlg.setWindowTitle(f"About {__app_name__}")
        apply_icon(dlg)
        dlg.setMinimumSize(440, 420)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setSpacing(8)
        about_layout.addStretch(1)

        logo = QLabel()
        logo.setPixmap(app_logo_pixmap(96))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(logo)

        title = QLabel(__app_name__)
        title.setObjectName("AboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(title)

        ver = QLabel(f"Version {__version__}")
        ver.setObjectName("AboutSubtitle")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(ver)

        desc = QLabel(
            "Local and cloud video management for\n"
            "XMeye / DVRIP and RTSP cameras."
        )
        desc.setObjectName("TileStatus")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(desc)
        about_layout.addStretch(1)

        copyr = QLabel("© 2026 Mantraix Software Solution. All Rights Reserved.")
        copyr.setObjectName("TileStatus")
        copyr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyr.setWordWrap(True)
        about_layout.addWidget(copyr)

        support = QLabel(
            'Support: <a href="mailto:MantraixSoftwareSolutions@gmail.com">'
            "MantraixSoftwareSolutions@gmail.com</a>"
        )
        support.setObjectName("TileStatus")
        support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        support.setOpenExternalLinks(True)
        about_layout.addWidget(support)
        tabs.addTab(about_tab, "About")

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        from .changelog import notes_text

        history = QTextEdit()
        history.setObjectName("ChangelogView")
        history.setReadOnly(True)
        history.setPlainText(notes_text())
        history_layout.addWidget(history)
        tabs.addTab(history_tab, "Version history")

        result = QLabel("")
        result.setObjectName("TileStatus")
        result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result.setWordWrap(True)
        layout.addWidget(result)

        check_btn = QPushButton("Check for updates")
        check_btn.clicked.connect(
            lambda: self._run_update_check(dlg, check_btn, result)
        )
        layout.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        dlg.exec()

    @staticmethod
    def _run_update_check(dlg: QDialog, button: QPushButton, result: QLabel) -> None:
        from . import events

        button.setEnabled(False)
        button.setText("Checking…")
        result.setText("")
        worker = UpdateWorker(dlg)

        def on_done(res: dict) -> None:
            state, message = res.get("bridge", ("error", "no result"))
            color = {"current": "#34d399", "available": "#fbbf24"}.get(state, "#f87171")
            result.setStyleSheet(f"color: {color};")
            result.setText(message)
            events.log("app", f"Update check: {message}")
            button.setEnabled(True)
            button.setText("Check for updates")

        worker.finished.connect(on_done)
        worker.start()

    def closeEvent(self, event) -> None:  # noqa: N802
        from . import events

        events.log("app", "StrataView closed.")
        if self._fs_view is not None:
            self._fs_view.close()
        self.refresh.stop()
        self.log_timer.stop()
        try:
            self.scheduler.timer.stop()
            self.scheduler.sweep_timer.stop()
        except Exception:
            pass
        for det in self.detectors.values():
            det.stop()
        for rec in self.recorders.values():
            rec.stop()
        for src in self.sources.values():
            src.stop()
        super().closeEvent(event)
