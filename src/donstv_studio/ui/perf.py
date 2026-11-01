"""Leistungsdaten des Studio-Laptops: CPU, RAM, LAN (F-68). Ohne Qt, damit alles ohne Oberfläche testbar ist.

Die Werte kommen direkt aus /proc (kein zusätzliches Paket) [ANNAHME: Zielsystem Debian 13, Linux]:
- /proc/stat: Zeile «cpu» mit den Zählern in USER_HZ-Ticks, Format siehe `man 5 proc`
  (https://man7.org/linux/man-pages/man5/proc.5.html, Abschnitt /proc/stat).
- /proc/meminfo: «MemTotal» und «MemAvailable» in kB (1024 Byte), ebenda, Abschnitt /proc/meminfo.
  Belegt = gesamt − verfügbar.
- /proc/net/dev: je Schnittstelle Empfangs- und Sendezähler in Byte, ebenda, Abschnitt /proc/net/dev.

Fehlt eine Datei oder ist sie nicht lesbar oder nicht auswertbar, liefert die Messung None; die
Oberfläche zeigt dann «–» und läuft weiter.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

HISTORY_LENGTH = 60  # Sekunden Verlauf, 1 Messung pro Sekunde
NO_VALUE = "–"

# Schnittstellen, die nicht zählen: Loopback und virtuelle (Docker, Container, Brücken, Tunnel).
IGNORED_EXACT = frozenset({"lo"})
IGNORED_PREFIXES = ("docker", "veth", "br-", "virbr", "tun", "tap")


@dataclass(frozen=True)
class ProcPaths:
    stat: Path = Path("/proc/stat")
    meminfo: Path = Path("/proc/meminfo")
    net_dev: Path = Path("/proc/net/dev")


# --- Einlesen -----------------------------------------------------------------------------------


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii", errors="replace")
    except OSError:
        return None


def parse_cpu(text: str) -> tuple[int, int] | None:
    """(Summe aller Ticks, Ticks im Leerlauf) aus der ersten Zeile «cpu» von /proc/stat.

    Reihenfolge der Felder: user nice system idle iowait irq softirq steal guest guest_nice. «guest»
    ist in «user» schon enthalten und wird nicht noch einmal gezählt. Leerlauf = idle + iowait.
    """
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "cpu":
            try:
                v = [int(x) for x in parts[1:9]]
            except ValueError:
                return None
            if len(v) < 4:
                return None
            idle = v[3] + (v[4] if len(v) > 4 else 0)
            return sum(v), idle
    return None


def read_cpu(path: Path = ProcPaths.stat) -> tuple[int, int] | None:
    text = _read(path)
    return parse_cpu(text) if text is not None else None


def parse_mem(text: str) -> tuple[int, int] | None:
    """(belegt, gesamt) in Byte aus /proc/meminfo; belegt = MemTotal − MemAvailable."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            try:
                values[key] = int(rest.split()[0]) * 1024  # Angabe in kB (1024 Byte)
            except (ValueError, IndexError):
                return None
    if "MemTotal" not in values or "MemAvailable" not in values or values["MemTotal"] <= 0:
        return None
    total = values["MemTotal"]
    used = min(max(total - values["MemAvailable"], 0), total)
    return used, total


def read_mem(path: Path = ProcPaths.meminfo) -> tuple[int, int] | None:
    text = _read(path)
    return parse_mem(text) if text is not None else None


def counts_interface(name: str) -> bool:
    """Gehört die Schnittstelle zur Summe? Nicht: «lo» und virtuelle (docker*, veth*, br-*, …)."""
    return name not in IGNORED_EXACT and not name.startswith(IGNORED_PREFIXES)


def parse_net(text: str) -> dict[str, tuple[int, int]] | None:
    """Schnittstelle -> (Empfangsbyte, Sendebyte) aus /proc/net/dev, ohne ignorierte Schnittstellen."""
    result: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        name, sep, rest = line.partition(":")
        if not sep:
            continue  # Kopfzeilen
        name = name.strip()
        fields = rest.split()
        if len(fields) < 9:
            continue
        try:
            rx, tx = int(fields[0]), int(fields[8])
        except ValueError:
            continue
        if counts_interface(name):
            result[name] = (rx, tx)
    return result if result or "Receive" in text else None


def read_net(path: Path = ProcPaths.net_dev) -> dict[str, tuple[int, int]] | None:
    text = _read(path)
    return parse_net(text) if text is not None else None


# --- Berechnen ----------------------------------------------------------------------------------


def cpu_percent(prev: tuple[int, int] | None, cur: tuple[int, int] | None) -> float | None:
    """Gesamtauslastung in Prozent (0 bis 100) aus zwei Messungen; None, wenn nicht berechenbar."""
    if prev is None or cur is None:
        return None
    d_total, d_idle = cur[0] - prev[0], cur[1] - prev[1]
    if d_total <= 0 or d_idle < 0:  # kein Zeitfortschritt oder Zähler zurückgesetzt
        return None
    return min(100.0, max(0.0, 100.0 * (d_total - d_idle) / d_total))


def counter_delta(prev: int, cur: int) -> int:
    """Zuwachs eines Zählers. Springt er zurück, ist er übergelaufen: 32 Bit, sonst 64 Bit."""
    if cur >= prev:
        return cur - prev
    wrap = 1 << 32 if prev < (1 << 32) else 1 << 64
    return cur + wrap - prev


def net_rates(
    prev: dict[str, tuple[int, int]] | None, cur: dict[str, tuple[int, int]] | None, seconds: float
) -> tuple[float, float] | None:
    """(Empfang, Senden) in Bit pro Sekunde, Summe über die Schnittstellen, die in beiden Messungen vorkommen.

    Eine Schnittstelle, die neu dazukommt oder verschwindet, verfälscht die Rate so nicht.
    """
    if prev is None or cur is None or seconds <= 0:
        return None
    rx = tx = 0
    for name, (c_rx, c_tx) in cur.items():
        if name in prev:
            rx += counter_delta(prev[name][0], c_rx)
            tx += counter_delta(prev[name][1], c_tx)
    return rx * 8 / seconds, tx * 8 / seconds


# --- Formatieren --------------------------------------------------------------------------------

GIB = 1024**3


def format_cpu(percent: float | None) -> str:
    return NO_VALUE if percent is None else f"{round(percent)} %"


def format_mem(mem: tuple[int, int] | None) -> str:
    """«5.3 / 15.5 GiB» (belegt / gesamt)."""
    if mem is None:
        return NO_VALUE
    return f"{mem[0] / GIB:.1f} / {mem[1] / GIB:.1f} GiB"


def _rate_parts(bits_per_s: float) -> tuple[str, str]:
    """(Zahl, Einheit) mit automatischer Einheit: kbit/s bis unter 1 Mbit/s, dann Mbit/s, dann Gbit/s."""
    kbit = max(bits_per_s, 0.0) / 1000
    if round(kbit) < 1000:
        return f"{round(kbit)}", "kbit/s"
    mbit = kbit / 1000
    if round(mbit, 1) < 1000:
        return f"{mbit:.1f}", "Mbit/s"
    return f"{min(mbit / 1000, 99.9):.1f}", "Gbit/s"


def format_net(rates: tuple[float, float] | None) -> str:
    """«↓ 3  ↑ 99 kbit/s»; haben beide Werte dieselbe Einheit, steht sie nur einmal am Ende."""
    if rates is None:
        return NO_VALUE
    (rx, rx_unit), (tx, tx_unit) = _rate_parts(rates[0]), _rate_parts(rates[1])
    if rx_unit == tx_unit:
        return f"↓ {rx}  ↑ {tx} {tx_unit}"
    return f"↓ {rx} {rx_unit}  ↑ {tx} {tx_unit}"


# Längste möglichen Texte je Feld (für die feste Breite, F-68).
LONGEST = {
    "cpu": "100 %",
    "ram": "999.9 / 999.9 GiB",
    "lan": "↓ 999.9 Mbit/s  ↑ 999.9 Mbit/s",
}
TITLES = {"cpu": "CPU", "ram": "RAM", "lan": "LAN"}
FIELDS = tuple(TITLES)


# --- Verlauf und Messer -------------------------------------------------------------------------


class History:
    """Die letzten 60 Werte; der älteste fällt heraus. Fehlende Messungen werden als 0 gezeichnet."""

    def __init__(self, length: int = HISTORY_LENGTH) -> None:
        self._values: deque[float] = deque([0.0] * length, maxlen=length)

    def add(self, value: float | None) -> None:
        self._values.append(0.0 if value is None else float(value))

    def values(self) -> list[float]:
        return list(self._values)

    def __len__(self) -> int:
        return len(self._values)


@dataclass
class Sample:
    cpu: float | None = None  # Prozent
    mem: tuple[int, int] | None = None  # (belegt, gesamt) in Byte
    net: tuple[float, float] | None = None  # (Empfang, Senden) in Bit/s


@dataclass
class Sampler:
    """Misst bei jedem Aufruf von `sample()` und rechnet gegen die vorige Messung. Kein Thread, kein Zeitgeber."""

    paths: ProcPaths = field(default_factory=ProcPaths)
    clock: Callable[[], float] = time.monotonic
    _cpu: tuple[int, int] | None = None
    _net: dict[str, tuple[int, int]] | None = None
    _time: float | None = None

    def reset(self) -> None:
        """Nach einer Pause: die nächste Messung setzt nur den Ausgangspunkt."""
        self._cpu = self._net = self._time = None

    def sample(self) -> Sample:
        now = self.clock()
        cpu, net, mem = (
            read_cpu(self.paths.stat),
            read_net(self.paths.net_dev),
            read_mem(self.paths.meminfo),
        )
        seconds = now - self._time if self._time is not None else 0.0
        result = Sample(
            cpu=cpu_percent(self._cpu, cpu),
            mem=mem,
            net=net_rates(self._net, net, seconds),
        )
        self._cpu, self._net, self._time = cpu, net, now
        return result


def graph_scale(name: str, values: Iterable[float], mem: tuple[int, int] | None) -> float:
    """Obergrenze der senkrechten Achse: CPU 100 %, RAM Gesamtgrösse, LAN grösster Wert (mind. 100 kbit/s)."""
    if name == "cpu":
        return 100.0
    if name == "ram":
        return float(mem[1]) if mem else 1.0
    return max(max(values, default=0.0), 100_000.0)
