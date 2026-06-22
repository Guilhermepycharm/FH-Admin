"""Compatibility wrapper for the legacy curses interface.

The maintained application entrypoint is ``fh_admin_tui.textual_app`` via
``./run.py``. The curses UI remains importable here for older users, but new
work should stay on the Textual path.
"""

from __future__ import annotations

from .legacy.tui import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
