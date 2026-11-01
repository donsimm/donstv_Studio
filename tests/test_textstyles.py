"""F-15: Textstile aus overlay-game-tool – Schlüssel, Migration, unveränderte Regeln."""

import re
from pathlib import Path

import pytest

from donstv_studio.core.store import MIGRATIONS, Store
from donstv_studio.overlays.models import (
    DEFAULT_TEXT_STYLE,
    TEXT_STYLE_LABELS,
    TEXT_STYLES,
    OverlayError,
    Source,
)
from donstv_studio.overlays.repository import OverlayRepository

ROOT = Path(__file__).parent.parent
REFERENCE = (ROOT / "docs/referenz/textstile-overlay-game-tool.css").read_text(encoding="utf-8")
CSS = (ROOT / "src/donstv_studio/overlays/web/overlay.css").read_text(encoding="utf-8")


def test_f15_style_keys_and_labels_as_in_original():
    assert TEXT_STYLES == ("comic", "thick", "plain", "none")
    assert DEFAULT_TEXT_STYLE == "comic"
    assert list(TEXT_STYLE_LABELS.values()) == ["Comic", "Comic dick", "Schlicht", "Ohne"]
    assert "comic_thick" not in TEXT_STYLES
    with pytest.raises(OverlayError, match="Stil"):
        Source(kind="text", x=0, y=0, width=5, height=5, props={"style": "comic_thick"})


def test_f15_css_rules_are_verbatim_from_reference():
    rules = re.findall(r"\.txt-(comic|thick|plain)\{.*?\}", REFERENCE, flags=re.DOTALL)
    assert rules == ["comic", "thick", "plain"]
    for m in re.finditer(r"\.txt-(?:comic|thick|plain)\{.*?\}", REFERENCE, flags=re.DOTALL):
        assert m.group(0) in CSS, f"Regel {m.group(0)[:20]} weicht von der Referenz ab"
    assert ".txt-none{text-shadow:none;filter:none}" in CSS
    assert "-webkit-text-stroke" not in CSS  # alter Nachbau ist weg


def test_f15_migration_comic_thick_to_thick(tmp_path):
    path = tmp_path / "a.db"
    old = Store(path, migrations=MIGRATIONS[:3])  # Stand vor der Migration
    with old.transaction() as db:
        db.execute("INSERT INTO overlays (id,name,width,height,output,token) VALUES ('o','A',10,10,'browser','t')")
        rows = [
            ("s1", "text", '{"text": "Hallo", "style": "comic_thick", "size": 40}'),
            ("s2", "text", '{"style": "comic"}'),
            ("s3", "text", '{"text": "ohne Stil"}'),
            ("s4", "image", '{"media_id": ""}'),
        ]
        for sid, kind, props in rows:
            db.execute("INSERT INTO sources VALUES (?,'o',?,0,0,5,5,0,0,1,?)", (sid, kind, props))
    assert old.schema_version == 3
    old.close()

    new = Store(path)  # alle Migrationen
    assert new.schema_version == MIGRATIONS[-1][0] >= 4
    by_id = {s.id: s.props for s in OverlayRepository(new).get("o").sources}
    assert by_id["s1"] == {"text": "Hallo", "style": "thick", "size": 40}  # übrige Werte bleiben
    assert by_id["s2"] == {"style": "comic"}
    assert by_id["s3"] == {"text": "ohne Stil"}  # kein Stil bleibt ohne Stil (Standard: comic)
    assert by_id["s4"] == {"media_id": ""}
    new.close()
    Store(path).close()  # erneutes Öffnen ändert nichts und bricht nicht
