"""Protokollierung mit Rotation. Tokens und Passwörter werden geschwärzt (Regel 7)."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Schwärzt «token=…», «password: …», «Bearer …» usw.
_REDACT = re.compile(
    r"(?i)((?:access_|refresh_|api_|device_)?token|device_code|passwort|password|secret|authorization|bearer|oauth)"
    r"(\"?\s*[=:]\s*\"?|\s+)((?:(?:bearer|oauth)\s+)?[^\s&'\",;]+)"
)


# Overlay-Adressen tragen das Token als «t=…» in der Abfrage (/o/<id>?t=…).
_REDACT_QUERY_T = re.compile(r"([?&]t=)[^\s&'\"]+")


def redact(text: str) -> str:
    """Schwärzt Tokens und Passwörter in einem Text (gleiche Regeln wie im Protokoll)."""
    return _REDACT_QUERY_T.sub(r"\1***", _REDACT.sub(r"\1\2***", text))


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


# uvicorn schreibt die Adresse samt Abfrage («WebSocket /o/<id>?t=<Token>» [accepted]/[rejected]/[closed],
# bei Stufe DEBUG auch «< GET /o/<id>/ws?t=…») auf den Logger «uvicorn.error», nicht auf «uvicorn.access».
# `access_log=False` betrifft nur «uvicorn.access»; deshalb schwärzen wir an den Loggern selbst.
# Quelle: uvicorn/protocols/websockets/*_impl.py (get_path_with_query_string).
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class DropAll(logging.Filter):
    """Verwirft jeden Datensatz. Für `uvicorn.access`: Zugriffsprotokoll ist ausgeschaltet (`access_log=False`)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return False


def redact_uvicorn_loggers() -> None:
    """Schwärzt die uvicorn-Logger und lässt `uvicorn.access` verstummen. Wirkt unabhängig von Handlern.

    Zu `uvicorn.access`: `access_log=False` setzt dort nur `handlers=[]` und `propagate=False`. uvicorn schaltet den
    Zugriffslog aber nach `access_logger.hasHandlers()` (uvicorn/protocols/http/h11_impl.py, `self.access_log =
    self.access_logger.hasHandlers()`). Hängt jemand einen Handler an diesen Logger, ist der Zugriffslog wieder an.
    pytest 9 tut das (`_pytest/logging.py`, `catching_logs.__enter__`: «Attach to all non-propagating loggers»);
    daher erschienen in Tests Zeilen mit dem Overlay-Token. Im Betrieb ohne so einen Handler bleibt er aus.
    Der Filter macht das unabhängig davon: auf `uvicorn.access` wird nichts mehr ausgegeben.
    """
    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactFilter) for f in logger.filters):
            logger.addFilter(RedactFilter())
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, DropAll) for f in access.filters):
        access.addFilter(DropAll())


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
