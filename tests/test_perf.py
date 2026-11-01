"""F-68: Berechnung und Formatierung der Leistungsanzeige (ohne Oberfläche, läuft immer)."""

import pytest

from donstv_studio.ui import perf

STAT_1 = "cpu  1000 0 500 8000 500 0 0 0 0 0\ncpu0 500 0 250 4000 250 0 0 0 0 0\nintr 1\n"
STAT_2 = "cpu  1100 0 540 8300 510 0 0 0 0 0\ncpu0 550 0 270 4150 255 0 0 0 0 0\nintr 2\n"

MEMINFO = "MemTotal:       16252928 kB\nMemFree:         1000000 kB\nMemAvailable:   10670000 kB\nBuffers: 1 kB\n"

NET_HEADER = (
    "Inter-|   Receive                                                |  Transmit\n"
    " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
)


def netdev(**ifaces):
    lines = [NET_HEADER]
    for name, (rx, tx) in ifaces.items():
        name = name.replace("_", "-")
        lines.append(f"{name:>6}: {rx} 10 0 0 0 0 0 0 {tx} 10 0 0 0 0 0 0\n")
    return "".join(lines)


# --- CPU ----------------------------------------------------------------------------------------

def test_f68_cpu_percent_from_two_measurements():
    a, b = perf.parse_cpu(STAT_1), perf.parse_cpu(STAT_2)
    assert a == (10000, 8500)  # Summe der ersten 8 Felder, Leerlauf = idle + iowait
    # Zuwachs: total 450, idle 310 -> belegt 140 -> 31.1 %
    assert perf.cpu_percent(a, b) == pytest.approx(100 * 140 / 450)
    assert perf.format_cpu(perf.cpu_percent(a, b)) == "31 %"


def test_f68_cpu_percent_stays_between_0_and_100():
    assert perf.cpu_percent((100, 100), (200, 200)) == 0.0  # alles Leerlauf
    assert perf.cpu_percent((100, 0), (200, 0)) == 100.0
    assert perf.cpu_percent((100, 50), (200, 40)) is None  # Leerlauf-Zähler zurück: nicht berechenbar
    assert perf.cpu_percent((0, 0), (1000, 1000)) == 0.0
    assert 0.0 <= perf.cpu_percent((0, 0), (10, 1)) <= 100.0


def test_f68_cpu_percent_none_without_progress_or_data():
    assert perf.cpu_percent((100, 50), (100, 50)) is None
    assert perf.cpu_percent((100, 50), (90, 40)) is None  # Zähler zurückgesetzt
    assert perf.cpu_percent(None, (1, 1)) is None
    assert perf.cpu_percent((1, 1), None) is None


@pytest.mark.parametrize("text", ["", "garbage", "cpu  a b c d\n", "cpu  1 2\n", "intr 1\n"])
def test_f68_parse_cpu_rejects_unusable_text(text):
    assert perf.parse_cpu(text) is None


# --- RAM ----------------------------------------------------------------------------------------

def test_f68_mem_used_is_total_minus_available():
    used, total = perf.parse_mem(MEMINFO)
    assert total == 16252928 * 1024
    assert used == (16252928 - 10670000) * 1024
    assert perf.format_mem((used, total)) == "5.3 / 15.5 GiB"


@pytest.mark.parametrize(
    "text",
    ["", "MemTotal: 100 kB\n", "MemAvailable: 100 kB\n", "MemTotal: abc kB\nMemAvailable: 1 kB\n", "MemTotal: 0 kB\nMemAvailable: 0 kB\n"],
)
def test_f68_parse_mem_rejects_unusable_text(text):
    assert perf.parse_mem(text) is None


def test_f68_mem_used_is_clamped_to_total():
    used, total = perf.parse_mem("MemTotal: 100 kB\nMemAvailable: 500 kB\n")
    assert 0 <= used <= total


# --- LAN ----------------------------------------------------------------------------------------

def test_f68_net_sums_physical_interfaces_and_skips_virtual_ones():
    text = netdev(lo=(999, 999), eth0=(1000, 2000), enp3s0=(10, 20), docker0=(5, 5), veth1a2b=(7, 7),
                  br_abc=(9, 9), virbr0=(3, 3), tun0=(4, 4), tap1=(6, 6), wlp2s0=(100, 200))  # fmt: skip
    assert sorted(perf.parse_net(text)) == ["enp3s0", "eth0", "wlp2s0"]
    assert not perf.counts_interface("lo") and perf.counts_interface("eth0") and perf.counts_interface("wlan0")
    assert perf.counts_interface("ifb0")  # nicht ausgeschlossen: Nutzer-Auswahl ist festgelegt, ifb* zählt (immer 0)


def test_f68_net_rates_in_bit_per_second_over_the_interval():
    a = perf.parse_net(netdev(eth0=(1000, 2000), lo=(5, 5)))
    b = perf.parse_net(netdev(eth0=(1000 + 375, 2000 + 12375), lo=(500, 500)))
    rx, tx = perf.net_rates(a, b, 1.0)
    assert (rx, tx) == (3000.0, 99000.0)  # 375 Byte = 3 kbit, 12375 Byte = 99 kbit
    assert perf.net_rates(a, b, 2.0) == (1500.0, 49500.0)
    assert perf.format_net((rx, tx)) == "↓ 3  ↑ 99 kbit/s"


def test_f68_net_counter_overflow_32_and_64_bit():
    assert perf.counter_delta(10, 25) == 15
    assert perf.counter_delta(2**32 - 100, 50) == 150  # 32-Bit-Zähler übergelaufen
    assert perf.counter_delta(2**40, 10) == 2**64 - 2**40 + 10  # 64-Bit-Zähler übergelaufen
    a = {"eth0": (2**32 - 125, 0)}
    b = {"eth0": (125, 0)}
    assert perf.net_rates(a, b, 1.0) == (2000.0, 0.0)  # 250 Byte


def test_f68_net_rates_ignore_interfaces_that_appear_or_vanish():
    a = {"eth0": (0, 0), "usb0": (10**9, 10**9)}
    b = {"eth0": (125, 125), "wlan0": (10**9, 10**9)}
    assert perf.net_rates(a, b, 1.0) == (1000.0, 1000.0)


def test_f68_net_rates_unusable_input():
    assert perf.net_rates(None, {}, 1.0) is None
    assert perf.net_rates({}, None, 1.0) is None
    assert perf.net_rates({}, {}, 0.0) is None
    assert perf.net_rates({}, {}, 1.0) == (0.0, 0.0)  # keine Schnittstelle: 0, kein Fehler
    assert perf.parse_net("") is None


# --- Formatieren --------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("bits", "text"),
    [
        (0, "0 kbit/s"),
        (499, "0 kbit/s"),
        (3000, "3 kbit/s"),
        (999_400, "999 kbit/s"),
        (999_600, "1.0 Mbit/s"),  # rundet nicht auf «1000 kbit/s»
        (1_000_000, "1.0 Mbit/s"),
        (94_500_000, "94.5 Mbit/s"),
        (999_900_000, "999.9 Mbit/s"),
        (1_000_000_000, "1.0 Gbit/s"),
        (10e9, "10.0 Gbit/s"),
        (10e12, "99.9 Gbit/s"),
    ],
)
def test_f68_rate_units_and_rounding(bits, text):
    number, unit = perf._rate_parts(bits)
    assert f"{number} {unit}" == text


def test_f68_net_text_shares_unit_or_names_both():
    assert perf.format_net((3000, 99000)) == "↓ 3  ↑ 99 kbit/s"
    assert perf.format_net((1.2e6, 3.4e6)) == "↓ 1.2  ↑ 3.4 Mbit/s"
    assert perf.format_net((1.2e6, 99000)) == "↓ 1.2 Mbit/s  ↑ 99 kbit/s"
    assert perf.format_net(None) == "–"


def test_f68_mem_and_cpu_text():
    assert perf.format_mem((0, 1024**3)) == "0.0 / 1.0 GiB"
    assert perf.format_mem(None) == "–" and perf.format_cpu(None) == "–"
    assert perf.format_cpu(0) == "0 %" and perf.format_cpu(100) == "100 %" and perf.format_cpu(3.6) == "4 %"


def test_f68_cpu_and_ram_texts_are_not_longer_than_the_longest_defined_text():
    for p in (0, 9.9, 50, 100):
        assert len(perf.format_cpu(p)) <= len(perf.LONGEST["cpu"])
    for used, total in ((0, 0.5), (999.9, 999.9), (5.3, 15.5)):
        assert len(perf.format_mem((int(used * perf.GIB), int(total * perf.GIB)))) <= len(perf.LONGEST["ram"])


def test_f68_gbit_texts_are_not_wider_than_the_longest_text():
    # «↓ 99.9 Gbit/s  ↑ 99.9 Gbit/s» (eine Einheit) und gemischt «↓ 99.9 Gbit/s  ↑ 999.9 Mbit/s» sind kürzer.
    for a, b in ((1e15, 1e15), (1e15, 999.9e6), (999.9e6, 1e15), (999.9e6, 999.9e6)):
        assert len(perf.format_net((a, b))) <= len(perf.LONGEST["lan"]), (a, b)


# --- Verlauf und Messer -------------------------------------------------------------------------

def test_f68_history_keeps_exactly_60_values_and_drops_the_oldest():
    h = perf.History()
    assert len(h) == 60 and h.values() == [0.0] * 60
    for i in range(1, 100):
        h.add(float(i))
    assert len(h) == 60
    assert h.values() == [float(i) for i in range(40, 100)]
    h.add(None)
    assert h.values()[-1] == 0.0 and len(h) == 60


def test_f68_sampler_with_test_files(tmp_path):
    paths = perf.ProcPaths(tmp_path / "stat", tmp_path / "meminfo", tmp_path / "net")
    paths.meminfo.write_text(MEMINFO)
    now = [100.0]
    s = perf.Sampler(paths=paths, clock=lambda: now[0])
    paths.stat.write_text(STAT_1)
    paths.net_dev.write_text(netdev(eth0=(1000, 2000)))
    first = s.sample()
    assert first.cpu is None and first.net is None  # erste Messung: nur Ausgangspunkt
    assert first.mem is not None
    now[0] = 101.0
    paths.stat.write_text(STAT_2)
    paths.net_dev.write_text(netdev(eth0=(1375, 14375)))
    second = s.sample()
    assert second.cpu == pytest.approx(100 * 140 / 450)
    assert second.net == (3000.0, 99000.0)
    s.reset()
    assert s.sample().cpu is None


def test_f68_sampler_survives_missing_and_unreadable_files(tmp_path):
    s = perf.Sampler(paths=perf.ProcPaths(tmp_path / "x", tmp_path / "y", tmp_path / "z"))
    for _ in range(3):
        sample = s.sample()
        assert (sample.cpu, sample.mem, sample.net) == (None, None, None)
    (tmp_path / "dir").mkdir()  # ein Ordner statt Datei: nicht lesbar
    s = perf.Sampler(paths=perf.ProcPaths(tmp_path / "dir", tmp_path / "dir", tmp_path / "dir"))
    assert s.sample().cpu is None


def test_f68_sampler_on_the_real_proc_of_this_machine():
    s = perf.Sampler()
    s.sample()
    sample = s.sample()
    if sample.cpu is not None:
        assert 0.0 <= sample.cpu <= 100.0
    if sample.mem is not None:
        assert 0 <= sample.mem[0] <= sample.mem[1]
    if sample.net is not None:
        assert sample.net[0] >= 0 and sample.net[1] >= 0


def test_f68_graph_scale():
    assert perf.graph_scale("cpu", [3.0], None) == 100.0
    assert perf.graph_scale("ram", [1.0], (5, 20)) == 20.0
    assert perf.graph_scale("lan", [10.0], None) == 100_000.0  # Mindestmass, damit Rauschen nicht gross aussieht
    assert perf.graph_scale("lan", [5e6, 1.0], None) == 5e6
