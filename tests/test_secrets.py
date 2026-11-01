"""Zugangsdaten: Ersatz und Auswahl."""

import logging
import stat

from donstv_studio.core import secrets as sec


def test_file_secrets_roundtrip_and_mode(tmp_path):
    s = sec.FileSecrets(tmp_path / "x" / "secrets.json")
    assert s.get("a") is None
    s.set("a", "1")
    s.set("b", "2")
    s.delete("a")
    s.delete("fehlt")
    assert s.get("a") is None and s.get("b") == "2"
    assert stat.S_IMODE((tmp_path / "x" / "secrets.json").stat().st_mode) == 0o600


def test_fallback_with_warning(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(sec.KeyringSecrets, "usable", staticmethod(lambda: False))
    with caplog.at_level(logging.WARNING):
        store = sec.open_secret_store(tmp_path)
    assert isinstance(store, sec.FileSecrets)
    assert "WARNUNG" in caplog.text


def test_keyring_chosen_when_usable(tmp_path, monkeypatch):
    monkeypatch.setattr(sec.KeyringSecrets, "usable", staticmethod(lambda: True))
    assert isinstance(sec.open_secret_store(tmp_path), sec.KeyringSecrets)


def test_keyring_unusable_in_headless_env(monkeypatch):
    import keyring
    from keyring.backends.fail import Keyring as Fail

    monkeypatch.setattr(keyring, "get_keyring", lambda: Fail())
    assert sec.KeyringSecrets.usable() is False
