"""Testnachricht in den Chat der Testverbindung schreiben (nur mit `DONSTV_TWITCH_FAKE=1` im Kern, P07).

Aufruf im Projektordner mit aktivierter Umgebung, während `donstv-core` läuft:

    python tools/fake_chat.py "!test"
    python tools/fake_chat.py --user Anna --badge moderator "!regeln"

Die Nachricht erscheint im Chat-Dock und löst Commands aus, als käme sie von Twitch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from donstv_studio.core.config import DEFAULT_API_PORT, Paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Testnachricht für die Testverbindung «Twitch»")
    parser.add_argument("text")
    parser.add_argument("--user", default="Testnutzer")
    parser.add_argument("--badge", action="append", default=[], help="z. B. subscriber, moderator, broadcaster")
    args = parser.parse_args()
    port = os.environ.get("DONSTV_CORE_PORT") or DEFAULT_API_PORT
    body = json.dumps({"user": args.user, "text": args.text, "badges": args.badge}).encode()
    try:
        token = Paths.from_xdg().token_file.read_text(encoding="utf-8").strip()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/bot/test/chat", data=body, method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )  # fmt: skip
        urllib.request.urlopen(req, timeout=5).close()
    except (OSError, urllib.error.URLError) as e:
        print(f"Fehler: {e}. Läuft «donstv-core» mit DONSTV_TWITCH_FAKE=1?", file=sys.stderr)
        return 1
    print("gesendet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
