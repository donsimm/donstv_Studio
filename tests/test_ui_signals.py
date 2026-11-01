"""Layout wird auch bei SIGTERM und SIGINT der Oberfläche gespeichert (offener Punkt aus P05)."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError, reason="PyQt6 ist nicht installierbar oder lädt nicht")

import httpx
from PyQt6.QtWidgets import QApplication

from donstv_studio.core.config import Paths
from donstv_studio.ui.signals import SignalBridge
from helpers import RunningService

SRC = str(Path(__file__).resolve().parents[1] / "src")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_signal_bridge_delivers_signals_into_the_qt_event_loop(signum):
    app = QApplication.instance() or QApplication(["donstv-tests"])
    old = signal.getsignal(signum)
    bridge = SignalBridge()
    got: list[int] = []
    bridge.received.connect(got.append)
    try:
        os.kill(os.getpid(), signum)
        end = time.time() + 5
        while not got and time.time() < end:
            app.processEvents()
            time.sleep(0.01)
        assert got == [int(signum)]
    finally:
        bridge.close()
    assert signal.getsignal(signum) == old  # alte Behandlung wiederhergestellt


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_ui_process_saves_layout_on_signal_and_exits_cleanly(tmp_path, signum):
    """Echter Prozess `donstv-studio` (offscreen) gegen einen echten Kern-Dienst: Signal senden, danach liegt das
    Layout im Kern."""
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "PYTHONPATH": SRC,
    }
    old_env = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")}
    os.environ.update({k: env[k] for k in old_env})
    try:
        paths = Paths.from_xdg()
    finally:
        for k, v in old_env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    port = free_port()
    env["DONSTV_CORE_PORT"] = str(port)
    core = RunningService(paths, port, free_port()).start()
    code = "import logging, sys; logging.basicConfig(level=logging.INFO, stream=sys.stderr); " \
           "from donstv_studio.ui.main import main; sys.exit(main())"  # fmt: skip
    proc = subprocess.Popen([sys.executable, "-c", code], env=env, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        ready = False
        end = time.time() + 60
        lines: list[str] = []
        while time.time() < end and not ready:
            line = proc.stderr.readline()
            if not line:
                break
            lines.append(line)
            ready = "Oberfläche bereit" in line
        assert ready, "Oberfläche startet nicht:\n" + "".join(lines)[-2000:]
        time.sleep(0.5)  # Kern-Verbindung und Einstellungen sind schon vor dem Anzeigen geholt
        headers = {"Authorization": f"Bearer {core.svc.token}"}
        assert "ui.dock_state" not in httpx.get(f"{core.base_url}/settings", headers=headers).json()
        proc.send_signal(signum)
        assert proc.wait(30) == 0  # sauberes Beenden
        saved = httpx.get(f"{core.base_url}/settings", headers=headers).json()
        assert saved["ui.theme"] == "dark"
        for key in ("ui.geometry", "ui.dock_state"):
            assert saved[key], key
            import base64

            assert saved[key].startswith("v3:") and base64.b64decode(saved[key][3:])  # Marke und gültiges Base64
        json.dumps(saved)
    finally:
        if proc.poll() is None:
            proc.kill()
        core.stop()
