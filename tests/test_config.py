"""F-03: Konfiguration, Pfade, Export/Import."""

import json

import pytest

from donstv_studio.core.config import Config, ConfigError, Paths
from donstv_studio.core.store import Store


def make(tmp_path, name="a.db"):
    return Config(Store(tmp_path / name))


def test_f03_roundtrip(tmp_path):
    a = make(tmp_path, "a.db")
    a.set("api.port", "9000")
    a.set("ui.theme", "dunkel")
    text = a.export_json()
    assert json.loads(text)["version"] == 1
    b = make(tmp_path, "b.db")
    b.import_json(text)
    assert b.export_data() == a.export_data()
    assert b.api_port == 9000


def test_f03_secrets_not_exported_or_stored(tmp_path):
    a = make(tmp_path)
    with pytest.raises(ConfigError):
        a.set("secret.twitch", "geheim")
    a._store.set_setting("token.x", "geheim")  # Altlast direkt in der Datenbank
    assert "geheim" not in a.export_json()


@pytest.mark.parametrize(
    "bad",
    [
        {"settings": {}},
        {"version": 99, "settings": {}},
        {"version": 1, "settings": {"a": 1}},
        {"version": 1, "settings": {"secret.a": "x"}},
        [],
    ],
)
def test_f03_invalid_import_rejected_and_state_kept(tmp_path, bad):
    a = make(tmp_path)
    a.set("k", "v")
    with pytest.raises(ConfigError):
        a.import_data(bad)
    assert a.get("k") == "v"
    with pytest.raises(ConfigError):
        a.import_json("kein json")


def test_f03_default_port(tmp_path):
    assert make(tmp_path).api_port == 8765


def test_f03_xdg_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "c"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "d"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "s"))
    p = Paths.from_xdg()
    assert p.config_dir == tmp_path / "c" / "donstv_studio"
    assert p.backup_dir == tmp_path / "d" / "donstv_studio" / "backups"
    assert p.log_file.parent == tmp_path / "s" / "donstv_studio" / "log"
