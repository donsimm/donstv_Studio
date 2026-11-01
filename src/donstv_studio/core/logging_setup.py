"""Protokollierung mit Rotation. Tokens und Passwörter werden geschwärzt (Regel 7)."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Schwärzt «token=…», «password: …», «Bearer …» usw.
_REDACT = re.compile(
    r"(?i)((?:access_|refresh_|api_)?token|passwort|password|secret|authorization|bearer)"
    r"(\s*[=:]\s*|\s+)([^\s&'\",;]+)"
)


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _REDACT.sub(r"\1\2***", record.getMessage())
        record.args = None
        return True


def setup_logging(log_file: Path, level: int = logging.INFO, console: bool = True) -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    ]
    if console:
        handlers.append(logging.StreamHandler())
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(RedactFilter())
        root.addHandler(h)
