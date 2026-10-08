"""StrataView VMS entry point.

Run with:
    python vms_app.py
"""

import sys

from PyQt6.QtWidgets import QApplication

from vms.main_window import MainWindow
from vms.resources import app_icon
from vms.settings import apply_saved
from vms.splash import show_splash, wait_for_first_live
from vms.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("StrataView")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    apply_saved()  # custom folders, if set in Settings
    splash = show_splash(app)
    window = MainWindow()
    wait_for_first_live(app, window, splash)
    window.show()
    splash.finish(window)
    window.maybe_first_run()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
