"""Regeln aus CLAUDE.md, die sich am Quelltext prüfen lassen (P08)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_SIGNAL_TYPES = {"str", "int", "float", "bool"}


def signal_signatures():
    """Alle `pyqtSignal(...)` in `src/` und `tools/`: (Datei, Zeile, Typen als Text)."""
    for path in sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("tools/*.py")]):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "pyqtSignal":
                yield path.relative_to(ROOT), node.lineno, [ast.unparse(a) for a in node.args]


def test_rule12_signals_carry_only_simple_types():
    """Regel 12: Signale tragen nur Zahlen, Text und Wahrheitswerte; Wörterbücher und Listen als JSON-Text."""
    found = list(signal_signatures())
    assert len(found) > 20  # die Suche findet die Signale überhaupt
    bad = [
        (str(f), line, types) for f, line, types in found if not set(types) <= ALLOWED_SIGNAL_TYPES
    ]
    assert bad == []
