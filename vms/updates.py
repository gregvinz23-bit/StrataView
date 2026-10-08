"""Update checking for StrataView.

What this checks (honestly scoped):
- The P2P bridge script we bundle is a lightly patched copy of an upstream
  open-source project. This compares the upstream file against the revision
  we last reviewed (BRIDGE_BASELINE_*). A mismatch means "upstream moved —
  needs human review before adopting", not "click to auto-update".
- StrataView itself ships as portable builds; there is no auto-update
  channel. New app versions come as new builds from your assistant.
"""

from __future__ import annotations

import hashlib
import os
import platform
import urllib.request

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:  # pragma: no cover
    pass

BRIDGE_UPSTREAM_URL = (
    "https://raw.githubusercontent.com/wire67/xmeye_cloud_to_rtsp"
    "/main/xmeye_cloud_to_rtsp.py"
)
# SHA-256 of the upstream file at our last review (2026-10-08).
# Our bundled copy additionally carries two local patches (password via
# environment, windowless ffmpeg), tracked separately from upstream drift.
BRIDGE_BASELINE_SHA256 = (
    "f71a50fd90d78b998bad53848357df167aeffb525fe93b876965e8fe15e6f168"
)


def fetch_upstream_sha(timeout: int = 20) -> tuple[str | None, str | None]:
    """Return (sha256_hex | None, error_message | None)."""
    try:
        req = urllib.request.Request(
            BRIDGE_UPSTREAM_URL, headers={"User-Agent": "StrataView-update-check"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if not data:
            return None, "empty response from update server"
        return hashlib.sha256(data).hexdigest(), None
    except Exception as exc:
        return None, f"could not reach update server ({exc})"


def check_now() -> dict:
    """Run the full check. Safe to call from a worker thread."""
    sha, err = fetch_upstream_sha()
    if err:
        bridge = ("error", err)
    elif sha == BRIDGE_BASELINE_SHA256:
        bridge = ("current", "Bridge script is up to date.")
    else:
        bridge = (
            "available",
            "Upstream bridge changed since our last review "
            f"({sha[:12]} vs {BRIDGE_BASELINE_SHA256[:12]}). "
            "Ask your assistant to review before updating.",
        )
    return {"bridge": bridge, "versions": component_versions()}


def component_versions() -> list[tuple[str, str]]:
    from vms import __app_name__, __version__

    items = [(__app_name__, __version__), ("Python", platform.python_version())]
    try:
        from PyQt6.QtCore import QT_VERSION_STR

        items.append(("PyQt6 (Qt)", QT_VERSION_STR))
    except ImportError:
        items.append(("PyQt6 (Qt)", "not installed"))
    for mod_name, label in (("cv2", "OpenCV"), ("numpy", "NumPy")):
        try:
            mod = __import__(mod_name)
            items.append((label, getattr(mod, "__version__", "installed")))
        except ImportError:
            items.append((label, "not installed"))
    return items
