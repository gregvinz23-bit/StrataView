"""First-run wizard: Welcome -> Add camera -> Done.

Shown automatically when StrataView starts with no cameras configured.
Businesslike tone, validated input, Cancel leaves an empty main window.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QComboBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from .resources import app_logo_pixmap, apply_icon


class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to StrataView")
        self.setSubTitle("Local and cloud video management for your cameras.")
        layout = QVBoxLayout(self)
        logo = QLabel()
        logo.setPixmap(app_logo_pixmap(96))
        layout.addWidget(logo)
        info = QLabel(
            "This wizard will help you add your first camera.\n"
            "You will need the camera's address or CloudID,\n"
            "username and password."
        )
        layout.addWidget(info)


class CameraPage(QWizardPage):
    LOGIN_TYPES = ["CloudID", "IP Address", "RTSP URL"]

    def __init__(self, parent=None, groups: list | None = None):
        super().__init__(parent)
        self.setTitle("Add your first camera")
        self.setSubTitle("Enter the connection details. All fields are required.")
        form = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Home CCTV")
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.addItems(groups or ["Default Group"])
        self.login_combo = QComboBox()
        self.login_combo.addItems(self.LOGIN_TYPES)
        self.addr_label = QLabel("CloudID:")
        self.addr_edit = QLineEdit()
        self.addr_edit.setPlaceholderText("e.g. ab12cd34ef567890")
        self.user_edit = QLineEdit("admin")
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Device name:", self.name_edit)
        form.addRow("Group:", self.group_combo)
        form.addRow("Login type:", self.login_combo)
        form.addRow(self.addr_label, self.addr_edit)
        form.addRow("Username:", self.user_edit)
        form.addRow("Password:", self.pass_edit)

        self.login_combo.currentTextChanged.connect(self._on_login_changed)
        self._on_login_changed(self.login_combo.currentText())

        # Live validation markers.
        for widget in (self.name_edit, self.addr_edit):
            widget.textChanged.connect(self.completeChanged.emit)

    def _on_login_changed(self, login: str) -> None:
        if login == "RTSP URL":
            self.addr_label.setText("RTSP URL:")
            self.addr_edit.setPlaceholderText("rtsp://user:pass@192.168.1.20:554/stream1")
        elif login == "CloudID":
            self.addr_label.setText("CloudID:")
            self.addr_edit.setPlaceholderText("e.g. ab12cd34ef567890")
        else:
            self.addr_label.setText("IP address:")
            self.addr_edit.setPlaceholderText("e.g. 10.20.30.121")

    def isComplete(self) -> bool:  # noqa: N802
        return bool(self.name_edit.text().strip() and self.addr_edit.text().strip())

    def config(self) -> dict:
        name = self.name_edit.text().strip()
        addr = self.addr_edit.text().strip()
        login = self.login_combo.currentText()
        group = self.group_combo.currentText().strip() or "Default Group"
        if login == "RTSP URL":
            cfg: dict = {"name": name, "type": "rtsp", "url": addr}
        else:
            cfg = {
                "name": name,
                "type": "dvrip",
                "user": self.user_edit.text().strip() or "admin",
                "password": self.pass_edit.text(),
                "port": 34567,
                "channel": 0,
            }
            if login == "CloudID":
                cfg["cloud_id"] = addr
                cfg["host"] = addr
            else:
                cfg["host"] = addr
        cfg["group"] = group
        cfg["login_type"] = login
        cfg["enabled"] = True
        return cfg


class DonePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Setup complete")
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)

    def initializePage(self) -> None:  # noqa: N802
        cfg = self.wizard().camera_config()
        self.summary.setText(
            f"Camera '{cfg['name']}' has been added.\n\n"
            "Connecting can take up to 30 seconds for cloud cameras.\n"
            "You can add more cameras later from the toolbar."
            if cfg else "No camera was added. You can add one later from the toolbar."
        )


class FirstRunWizard(QWizard):
    def __init__(self, parent=None, groups: list | None = None):
        super().__init__(parent)
        self.setWindowTitle("StrataView setup")
        apply_icon(self)
        # ClassicStyle renders titles as plain labels, which respects the
        # dark theme. ModernStyle paints a hardcoded white banner.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self._camera_page = CameraPage(groups=groups)
        self.addPage(WelcomePage())
        self.addPage(self._camera_page)
        self.addPage(DonePage())
        self.setButtonText(QWizard.WizardButton.FinishButton, "Done")

    def camera_config(self) -> dict | None:
        if not self._camera_page.isComplete():
            return None
        return self._camera_page.config()

    @staticmethod
    def check_duplicate(parent, name: str, existing: list[str]) -> bool:
        if name in existing:
            QMessageBox.warning(
                parent, "StrataView setup",
                f"A camera named '{name}' already exists. Please choose another name.",
            )
            return True
        return False
