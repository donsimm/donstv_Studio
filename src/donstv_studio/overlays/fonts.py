"""Installierte Systemschriften (F-38) über fontconfig (`fc-list`).

Hinweis: Die Schrift wird in OBS auf dem Streaming-PC gezeichnet. Eine Schrift, die nur auf
dem Laptop installiert ist, fehlt dort. Eigene Schriftdateien (F-39) folgen später.
"""

from __future__ import annotations

import asyncio
import contextlib
import re

from donstv_studio.overlays.models import DEFAULT_FONT

_FONT = re.compile(r"^[\w .,+&()\-]{1,100}$")


def parse_fc_list(output: str) -> list[str]:
    names: dict[str, str] = {}
    for line in output.splitlines():
        for name in line.split(","):
            name = name.strip()
            if name and _FONT.match(name) and name.casefold() not in names:
                names[name.casefold()] = name
    return sorted(names.values(), key=str.casefold)


async def list_system_fonts(timeout: float = 5.0) -> list[str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "fc-list", ":", "family",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )  # fmt: skip
    except OSError:
        return []
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        return []
    return parse_fc_list(out.decode("utf-8", "replace"))


async def font_choices() -> dict:
    """Standard («Be Vietnam Pro») plus installierte Systemschriften."""
    fonts = [f for f in await list_system_fonts() if f.casefold() != DEFAULT_FONT.casefold()]
    return {"default": DEFAULT_FONT, "fonts": fonts}
