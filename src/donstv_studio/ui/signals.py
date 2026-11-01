"""SIGTERM und SIGINT in der Qt-Ereignisschleife behandeln (Layout beim Beenden von aussen speichern).

Python-Signalbehandler laufen nur, wenn der Interpreter Bytecode ausführt; in `QApplication.exec()` wartet aber Qt.
Deshalb schreibt Python die Signalnummer in einen Wakeup-Descriptor (`signal.set_wakeup_fd`), den ein
`QSocketNotifier` überwacht. Quelle: https://doc.qt.io/qt-6/unix-signals.html und
https://docs.python.org/3/library/signal.html#signal.set_wakeup_fd
"""

from __future__ import annotations

import signal
import socket

from PyQt6.QtCore import QObject, QSocketNotifier, pyqtSignal


class SignalBridge(QObject):
    received = pyqtSignal(int)  # Signalnummer

    def __init__(
        self,
        signums: tuple[int, ...] = (signal.SIGTERM, signal.SIGINT),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._signums = signums
        self._rsock, self._wsock = socket.socketpair()
        self._rsock.setblocking(False)
        self._wsock.setblocking(False)
        self._old_fd = signal.set_wakeup_fd(self._wsock.fileno(), warn_on_full_buffer=False)
        # Ein Python-Behandler muss gesetzt sein, sonst schreibt Python nichts in den Descriptor.
        self._old_handlers = {s: signal.signal(s, lambda *_: None) for s in signums}
        self._notifier = QSocketNotifier(self._rsock.fileno(), QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._read)

    def _read(self) -> None:
        try:
            data = self._rsock.recv(64)
        except BlockingIOError:
            return
        for num in data:
            if num in self._signums:
                self.received.emit(num)

    def close(self) -> None:
        """Alte Behandler wiederherstellen."""
        self._notifier.setEnabled(False)
        signal.set_wakeup_fd(self._old_fd)
        for s, h in self._old_handlers.items():
            signal.signal(s, h)
        self._rsock.close()
        self._wsock.close()
