"""F-16: Bibliothek, Prüfung von Typ und Grösse beim Speichern."""

import pytest

from donstv_studio.core.store import Store
from donstv_studio.overlays import media as m
from donstv_studio.overlays.media import MediaLibrary
from helpers import solid_png

JPG = b"\xff\xd8\xff\xe0" + b"\0" * 64
GIF = b"GIF89a" + b"\0" * 64
WEBP = b"RIFF\x24\0\0\0WEBPVP8 " + b"\0" * 40
WEBM = b"\x1a\x45\xdf\xa3" + b"\x42\x82\x84webm" + b"\0" * 40
SVG = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'


async def chunks(data: bytes, size: int = 7000):
    for i in range(0, len(data), size):
        yield data[i : i + size]


@pytest.fixture
def lib(tmp_path):
    return MediaLibrary(Store(tmp_path / "a.db"), tmp_path / "media")


@pytest.mark.parametrize(
    ("data", "ext", "mime"),
    [
        (solid_png(2, 2, (1, 2, 3, 255)), "png", "image/png"),
        (JPG, "jpg", "image/jpeg"),
        (GIF, "gif", "image/gif"),
        (WEBP, "webp", "image/webp"),
        (WEBM, "webm", "video/webm"),
        (SVG, "svg", "image/svg+xml"),
    ],
)
async def test_f16_allowed_types_detected_by_content(lib, data, ext, mime):
    # Dateiname lügt absichtlich: erkannt wird am Inhalt
    item = await lib.save("irgendwas.txt", chunks(data))
    assert (item.ext, item.mime, item.size) == (ext, mime, len(data))
    assert lib.path_of(item).read_bytes() == data
    assert lib.get(item.id) == item


@pytest.mark.parametrize(
    "data",
    [
        b"Hallo Welt, das ist Text",
        b"MZ\x90\x00 programm",
        b"<html><body>hi</body></html>",
        b"<svg"[:3],
    ],
)
async def test_f16_wrong_type_rejected_even_with_image_extension(lib, data):
    with pytest.raises(m.UnsupportedTypeError):
        await lib.save("bild.png", chunks(data))
    assert lib.list() == []
    assert list(lib._dir.iterdir()) == []  # keine Reste


async def test_f16_empty_rejected(lib):
    with pytest.raises(m.UnsupportedTypeError, match="leer"):
        await lib.save("a.png", chunks(b""))


async def test_f16_too_large_rejected_and_cleaned_up(lib):
    big = solid_png(2, 2, (0, 0, 0, 255)) + b"\0" * (m.MAX_BYTES)  # 25 MB + Kopf
    with pytest.raises(m.TooLargeError, match="25 MB"):
        await lib.save("gross.png", chunks(big, 1 << 20))
    assert lib.list() == [] and list(lib._dir.iterdir()) == []


async def test_f16_exactly_25mb_allowed(lib):
    head = solid_png(1, 1, (0, 0, 0, 255))
    data = head + b"\0" * (m.MAX_BYTES - len(head))
    item = await lib.save("genau.png", chunks(data, 1 << 20))
    assert item.size == m.MAX_BYTES


@pytest.mark.parametrize(
    "evil",
    [
        b"<svg><script>alert(1)</script></svg>",
        b'<svg onload="x()"/>',
        b'<svg><a href="javascript:x()"/></svg>',
        b"<svg><foreignObject/></svg>",
    ],
)
async def test_f16_svg_with_active_content_rejected(lib, evil):
    with pytest.raises(m.UnsupportedTypeError, match="aktive Inhalte"):
        await lib.save("x.svg", chunks(evil))


async def test_f16_names_are_cleaned(lib):
    item = await lib.save("../../etc/pass\x00wd.png", chunks(solid_png(1, 1, (0, 0, 0, 255))))
    assert item.name == "passwd.png"
    assert lib.path_of(item).parent == lib._dir


async def test_f16_reusable_and_delete_refused_while_used(lib, tmp_path):
    item = await lib.save("a.png", chunks(solid_png(1, 1, (0, 0, 0, 255))))
    store = lib._store
    with store.transaction() as db:
        db.execute(
            "INSERT INTO overlays (id,name,width,height,output,token) VALUES ('o1','A',10,10,'browser','t1')"
        )
        db.execute(
            "INSERT INTO overlays (id,name,width,height,output,token) VALUES ('o2','B',10,10,'browser','t2')"
        )
        for sid, oid in (("s1", "o1"), ("s2", "o1"), ("s3", "o2")):  # mehrfach verwendet
            db.execute(
                "INSERT INTO sources VALUES (?,?,?,0,0,5,5,0,0,1,?)",
                (sid, oid, "image", f'{{"media_id": "{item.id}"}}'),
            )
    assert sorted(lib.used_by(item.id)) == ["o1", "o2"]
    with pytest.raises(m.InUseError):
        lib.delete(item.id)
    with store.transaction() as db:
        db.execute("DELETE FROM sources")
    lib.delete(item.id)
    assert lib.list() == [] and not lib.path_of(item).exists()
    with pytest.raises(m.MediaNotFoundError):
        lib.delete(item.id)
