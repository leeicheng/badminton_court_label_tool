from __future__ import annotations

import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

from gui_tool import MainWindow as MarkerWindow
from output_tool.output_tool_gui import MainWindow as OutputWindow
from video_split_tool.split_tool import VideoFrameExtractor


class Launcher(QWidget):
    """Simple window to choose which tool to start."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tool Launcher")
        layout = QVBoxLayout(self)

        btn_marker = QPushButton("32-Point Marker")
        btn_output = QPushButton("Dataset Builder")
        btn_split = QPushButton("Video Split Tool")

        layout.addWidget(btn_marker)
        layout.addWidget(btn_output)
        layout.addWidget(btn_split)

        btn_marker.clicked.connect(self.open_marker)
        btn_output.clicked.connect(self.open_output)
        btn_split.clicked.connect(self.open_split)

        self._marker_window: MarkerWindow | None = None
        self._output_window: OutputWindow | None = None
        self._split_window: VideoFrameExtractor | None = None

    # --- open windows ---
    def open_marker(self) -> None:
        if self._marker_window is None:
            self._marker_window = MarkerWindow()
        self._marker_window.show()

    def open_output(self) -> None:
        if self._output_window is None:
            self._output_window = OutputWindow()
        self._output_window.show()

    def open_split(self) -> None:
        if self._split_window is None:
            self._split_window = VideoFrameExtractor()
        self._split_window.show()


def main() -> None:
    app = QApplication(sys.argv)
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
