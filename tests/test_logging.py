"""Protokoll: Rotation und Schwärzung."""

import logging

from donstv_studio.core.logging_setup import setup_logging


def test_tokens_redacted_in_log(tmp_path):
    f = tmp_path / "l.log"
    setup_logging(f, console=False)
    logging.getLogger("t").warning("GET /ws/events?token=abc123&x=1 password=hunter2 Bearer xyz")
    for h in logging.getLogger().handlers:
        h.flush()
    text = f.read_text()
    for geheim in ("abc123", "hunter2", "xyz"):
        assert geheim not in text
    assert "***" in text


def test_overlay_token_in_query_t_redacted(tmp_path):
    f = tmp_path / "l.log"
    setup_logging(f, console=False)
    logging.getLogger("t").warning("GET /o/abc?t=GEHEIMES_TOKEN HTTP/1.1 und /ws?x=1&t=ANDERES")
    for h in logging.getLogger().handlers:
        h.flush()
    text = f.read_text()
    assert "GEHEIMES_TOKEN" not in text and "ANDERES" not in text
