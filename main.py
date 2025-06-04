#!/usr/bin/env python3
"""Entry point for selecting different GUI tools."""
from __future__ import annotations

import sys
from PyQt6.QtWidgets import QApplication

from launcher import Launcher


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Launcher()
    win.show()
    sys.exit(app.exec())
