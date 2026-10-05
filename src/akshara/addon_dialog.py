"""Dialog that installs the neural-voice add-on with live installer output."""

from __future__ import annotations

from PyQt6.QtCore import QProcess, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .tts import addon


class AddonInstallDialog(QDialog):
    installed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, command: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Install neural voices")
        self.resize(640, 420)
        self._command = command if command is not None else addon.install_command()

        info = QLabel(
            "Downloads the Kokoro neural speech engine and a CPU build of PyTorch "
            "(about 1 GB) into:<br><code>"
            f"{addon.addon_dir()}</code><br><br>"
            "The voice model itself (~330 MB) downloads the first time you press Read."
        )
        info.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("monospace", 9))
        self.status = QLabel("")
        self.status.setObjectName("secondary")

        self.install_btn = QPushButton("Install")
        self.install_btn.setObjectName("accentButton")
        self.install_btn.clicked.connect(self.start)
        self.close_btn = QPushButton("Cancel")
        self.close_btn.clicked.connect(self._cancel_or_close)
        buttons = QHBoxLayout()
        buttons.addWidget(self.status, 1)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.install_btn)

        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.log, 1)
        lay.addLayout(buttons)

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(self._error)

        if self._command is None:
            self.install_btn.setEnabled(False)
            self.status.setText("No installer found: this Python has no pip and uv is not on PATH.")

    def start(self) -> None:
        if not self._command or self.proc.state() != QProcess.ProcessState.NotRunning:
            return
        addon.addon_dir().mkdir(parents=True, exist_ok=True)
        self.log.appendPlainText("$ " + " ".join(self._command))
        self.install_btn.setEnabled(False)
        self.close_btn.setText("Cancel")
        self.status.setText("Installing… this can take several minutes.")
        self.proc.start(self._command[0], self._command[1:])

    def _read(self) -> None:
        data = bytes(self.proc.readAllStandardOutput().data()).decode(errors="replace")
        for line in data.splitlines():
            if line.strip():
                self.log.appendPlainText(line)

    def _finished(self, code: int, _status) -> None:
        self.close_btn.setText("Close")
        if code == 0:
            addon.mark_complete()
            addon.activate()
            self.status.setText("Installed. Choose “Neural (Kokoro)” as the engine.")
            self.installed.emit()
        else:
            self.status.setText(f"Installation failed (exit code {code}). See the log above.")
            self.install_btn.setEnabled(True)

    def _error(self, _err) -> None:
        self.status.setText(f"Could not start the installer: {self.proc.errorString()}")
        self.install_btn.setEnabled(True)
        self.close_btn.setText("Close")

    def _cancel_or_close(self) -> None:
        if self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(3000)
            self.status.setText("Cancelled.")
            return
        self.reject()
