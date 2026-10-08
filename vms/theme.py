"""Modern dark theme for StrataView VMS (Qt stylesheet + Fusion style)."""

ACCENT = "#2dd4bf"      # teal
ACCENT_DIM = "#134e4a"
DANGER = "#f87171"      # soft red
BG = "#11151c"          # app background
PANEL = "#1a212c"       # toolbar / panels
FIELD = "#0d1219"       # inputs / lists
BORDER = "#2b3543"
TEXT = "#e6eaf0"
MUTED = "#8b96a5"

MODERN_QSS = f"""
* {{ outline: none; }}
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}

/* ---------- menu bar / menus ---------- */
QMenuBar {{
    background: {PANEL};
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
    padding: 2px 6px;
}}
QMenuBar::item {{
    padding: 5px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: #2a3546;
}}
QMenu {{
    background: #161c26;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 22px 7px 30px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACCENT_DIM};
}}
QMenu::item:checked {{
    font-weight: 700;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}
QMenu::icon {{
    left: 8px;
}}

/* ---------- toolbar ---------- */
QToolBar#MainToolbar {{
    background: {PANEL};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 6px 8px;
}}
QToolBar#MainToolbar QToolButton {{
    background: transparent;
    color: #dbe2ec;
    padding: 7px 12px;
    border-radius: 6px;
    font-weight: 600;
}}
QToolBar#MainToolbar QToolButton:hover {{
    background: #2a3546;
}}
QToolBar#MainToolbar QToolButton:checked {{
    background: #3a1d22;
    color: {DANGER};
    border: 1px solid #7f2b33;
}}
QToolBar#MainToolbar QLabel {{
    color: {MUTED};
}}
QLabel#BrandLabel {{
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    padding-right: 6px;
}}

/* ---------- wizard ---------- */
QWizard {{
    background: {BG};
}}
QWizardPage {{
    background: {BG};
    color: {TEXT};
}}

/* ---------- sidebar camera list ---------- */
QFrame#SidePanel {{
    background: #141a23;
    border: none;
    border-right: 1px solid {BORDER};
}}
QLabel#SideHeader {{
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    padding: 2px 4px;
}}
QListWidget#CamList {{
    border: none;
    background: transparent;
}}
QListWidget#CamList::item {{
    padding: 0px;
    margin-bottom: 4px;
    background: {PANEL};
    border: 1px solid #232c38;
    border-radius: 6px;
}}
QListWidget#CamList::item:selected {{
    background: #1e3a37;
    border: 1px solid {ACCENT};
}}

/* ---------- video tiles ---------- */
VideoTile {{
    background: #05070a;
    border: 1px solid #232c38;
    border-radius: 8px;
}}
VideoTile[selected="true"] {{
    border: 2px solid {ACCENT};
}}
QWidget#TileBar {{
    background: rgba(10, 14, 20, 230);
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}}
QLabel#TileTitle {{
    color: #ffffff;
    font-weight: 700;
}}
QLabel#TileDot {{
    font-size: 14px;
}}
QLabel#TileRec {{
    color: {DANGER};
    font-weight: 700;
}}
QLabel#TileStatus {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#TileVideo {{
    background: black;
    color: #5b6675;
    font-size: 14px;
}}
QLabel#HintLabel {{
    color: {MUTED};
    font-size: 15px;
}}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    color: #5b6675;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: #161c26;
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: #243041;
    border: 1px solid #334052;
    padding: 7px 14px;
    border-radius: 6px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: #2e3d52;
}}
QPushButton:pressed {{
    background: #1b2431;
}}
QPushButton#PrimaryButton {{
    background: #0d9488;
    border: none;
}}
QPushButton#PrimaryButton:hover {{
    background: #14b8a6;
}}
QPushButton#DangerButton {{
    background: #7f2b33;
    border: none;
}}
QPushButton#DangerButton:hover {{
    background: #9b3540;
}}

/* ---------- lists / sliders / misc ---------- */
QListWidget {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background: {ACCENT_DIM};
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: #232c38;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    margin: -5px 0;
    background: {ACCENT};
    border-radius: 7px;
}}
QStatusBar {{
    background: #141a23;
    color: #9aa7b8;
}}
QStatusBar::item {{
    border: none;
}}
QDockWidget#LogDock {{
    color: {TEXT};
}}
QDockWidget#LogDock::title {{
    background: #141a23;
    padding: 4px 8px;
}}
QListWidget#LogView {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
}}
QLabel#AboutTitle {{
    color: #ffffff;
    font-weight: 700;
    font-size: 22px;
}}
QLabel#AboutSubtitle {{
    color: {MUTED};
    font-size: 14px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {BG};
}}
QTabWidget::tab-bar {{
    alignment: center;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 7px 18px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTextEdit#ChangelogView {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {MUTED};
}}
QMessageBox {{
    background: {BG};
}}
QToolTip {{
    background: #1e2530;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""


def apply_theme(app) -> None:
    """Apply Fusion style + the modern dark stylesheet."""
    app.setStyle("Fusion")
    app.setStyleSheet(MODERN_QSS)
