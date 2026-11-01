"""Einstiegspunkt `donstv-core`."""

from __future__ import annotations

import asyncio

from donstv_studio.core.config import Paths
from donstv_studio.core.logging_setup import setup_logging
from donstv_studio.core.service import Service


def main() -> int:
    paths = Paths.from_xdg()
    paths.ensure()
    setup_logging(paths.log_file)
    asyncio.run(Service(paths).run())
    return 0
