"""F-41 bis F-45: Commands, Ausführung, Protokoll und Chat mit der Testverbindung FakeTwitch (ohne Netz)."""

import pytest

from donstv_studio.bot import log as botlog
from donstv_studio.bot.commands import CommandError, CommandRepository
from donstv_studio.bot.engine import CHAT_HISTORY, CommandEngine, first_word, render
from donstv_studio.bot.executor import ActionError, ActionExecutor
from donstv_studio.bot.log import BotLog
from donstv_studio.core.bus import EventBus
from donstv_studio.core.connections.fake_twitch import FakeTwitch
from donstv_studio.core.store import Store


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
async def bot(tmp_path):
    bus = EventBus()
    store = Store(tmp_path / "bot.db")
    twitch = FakeTwitch(bus)
    await twitch.start()
    log = BotLog(store, bus)
    repo = CommandRepository(store)
    clock = Clock()
    engine = CommandEngine(bus, repo, ActionExecutor(lambda: twitch, log), log, lambda: twitch, clock)
    events = []

    async def collect(e):
        events.append(e)

    bus.subscribe("*", collect)
    yield type("Bot", (), {"bus": bus, "store": store, "twitch": twitch, "log": log, "repo": repo,
                           "clock": clock, "engine": engine, "events": events})  # fmt: skip
    store.close()


async def say(bot, *args, **kw):
    """Chat-Nachricht erzeugen und warten, bis ausgelöste Commands fertig sind."""
    payload = await bot.twitch.inject(*args, **kw)
    await bot.engine.drain()
    return payload


def kinds(bot):
    return [e["kind"] for e in bot.log.recent()]


# --- F-43: Commands verwalten -----------------------------------------------------------------

def test_f43_create_update_duplicate_delete(tmp_path):
    repo = CommandRepository(Store(tmp_path / "c.db"))
    cmd = repo.create({"name": "Regeln", "trigger": "!regeln", "response": "Sei nett, {user}",
                       "permission": "everyone", "cooldown_global": 30, "cooldown_user": 60})  # fmt: skip
    assert cmd.enabled and cmd.cooldown_global == 30 and cmd.cooldown_user == 60
    assert repo.update(cmd.id, {"enabled": False}).enabled is False
    dup = repo.duplicate(cmd.id)
    assert dup.trigger == "!regeln2" and dup.name == "Regeln (Kopie)" and dup.enabled is False
    assert [c.trigger for c in repo.list()] == ["!regeln", "!regeln2"]
    assert repo.delete(cmd.id) and not repo.delete(cmd.id)
    assert [c.id for c in repo.list()] == [dup.id]


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "", "trigger": "!a"},
        {"name": "A", "trigger": "zwei worte"},
        {"name": "A", "trigger": "!a", "permission": "admin"},
        {"name": "A", "trigger": "!a", "cooldown_global": -1},
        {"name": "A", "trigger": "!a", "cooldown_user": 1.5},
        {"name": "A", "trigger": "!a", "response": "x" * 501},
        {"name": "A", "trigger": "!a", "unbekannt": 1},
        {"trigger": "!a"},
    ],
)
def test_f43_invalid_fields_are_rejected(tmp_path, fields):
    with pytest.raises(CommandError):
        CommandRepository(Store(tmp_path / "c.db")).create(fields)


def test_f43_trigger_is_unique_ignoring_case(tmp_path):
    repo = CommandRepository(Store(tmp_path / "c.db"))
    repo.create({"name": "A", "trigger": "!Test"})
    with pytest.raises(CommandError, match="gibt es schon"):
        repo.create({"name": "B", "trigger": "!test"})


# --- F-44: Ausführung ---------------------------------------------------------------------------

async def test_f44_command_replies_with_placeholder(bot):
    bot.repo.create({"name": "Test", "trigger": "!test", "response": "Hallo {user}, alles klar!"})
    await say(bot, "Anna", "!test bitte")
    assert bot.twitch.sent == ["Hallo Anna, alles klar!"]
    await say(bot, "Anna", "!testen")  # anderes Wort: keine Antwort
    await say(bot, "Anna", "kein !test am Anfang")
    assert len(bot.twitch.sent) == 1
    assert "command" in kinds(bot)


async def test_f44_matching_ignores_case_and_invisible_chars(bot):
    bot.repo.create({"name": "Test", "trigger": "!test", "response": "ok"})
    await say(bot, "Ben", "!TEST \U000e0000")
    assert bot.twitch.sent == ["ok"]


async def test_f44_disabled_command_does_nothing(bot):
    bot.repo.create({"name": "Test", "trigger": "!test", "response": "ok", "enabled": False})
    await say(bot, "Ben", "!test")
    assert bot.twitch.sent == []


@pytest.mark.parametrize(
    ("permission", "badges", "allowed"),
    [
        ("everyone", [], True),
        ("subscriber", [], False),
        ("subscriber", ["subscriber"], True),
        ("subscriber", ["founder"], True),
        ("subscriber", ["moderator"], True),
        ("moderator", ["subscriber"], False),
        ("moderator", ["moderator"], True),
        ("moderator", ["vip"], False),
        ("broadcaster", ["moderator"], False),
        ("broadcaster", ["broadcaster"], True),
        ("moderator", ["broadcaster"], True),
    ],
)
async def test_f44_permission(bot, permission, badges, allowed):
    bot.repo.create({"name": "P", "trigger": "!p", "response": "ja", "permission": permission})
    await say(bot, "Cleo", "!p", badges)
    assert bot.twitch.sent == (["ja"] if allowed else [])
    if not allowed:
        entry = bot.log.recent()[-1]
        assert entry["kind"] == botlog.REJECTED_PERMISSION and "Cleo" in entry["message"]


async def test_f44_global_cooldown(bot):
    bot.repo.create({"name": "C", "trigger": "!c", "response": "r", "cooldown_global": 30})
    await say(bot, "A", "!c")
    bot.clock.t += 10
    await say(bot, "B", "!c")  # anderer Nutzer, aber globaler Cooldown
    assert bot.twitch.sent == ["r"]
    entry = bot.log.recent()[-1]
    assert entry["kind"] == botlog.REJECTED_COOLDOWN and entry["data"]["cooldown"] == "global"
    assert entry["data"]["remaining"] == 20
    bot.clock.t += 20
    await say(bot, "B", "!c")
    assert bot.twitch.sent == ["r", "r"]


async def test_f44_user_cooldown(bot):
    bot.repo.create({"name": "C", "trigger": "!c", "response": "r", "cooldown_user": 60})
    await say(bot, "A", "!c")
    await say(bot, "B", "!c")  # anderer Nutzer: erlaubt
    bot.clock.t += 30
    await say(bot, "A", "!c")  # derselbe Nutzer: gesperrt
    assert bot.twitch.sent == ["r", "r"]
    assert bot.log.recent()[-1]["data"]["cooldown"] == "pro Nutzer"
    bot.clock.t += 30
    await say(bot, "A", "!c")
    assert len(bot.twitch.sent) == 3


async def test_f44_rejected_attempt_does_not_restart_cooldown(bot):
    bot.repo.create({"name": "C", "trigger": "!c", "response": "r", "cooldown_global": 30})
    await say(bot, "A", "!c")
    bot.clock.t += 29
    await say(bot, "A", "!c")
    bot.clock.t += 1
    await say(bot, "A", "!c")
    assert len(bot.twitch.sent) == 2


async def test_f44_no_loop_on_own_messages(bot):
    # Die Antwort enthält selbst den Befehl; das Echo des Bot-Kontos darf nichts auslösen.
    bot.repo.create({"name": "L", "trigger": "!loop", "response": "!loop"})
    await say(bot, "A", "!loop")
    assert bot.twitch.sent == ["!loop"]
    chat = [e for e in bot.events if e.type == "twitch.chat.message"]
    # Echo kam an (wegen der Zustellung innerhalb des Sendens vor dem Original), wurde aber nicht ausgeführt
    assert len(chat) == 2 and sorted(e.payload["from_bot"] for e in chat) == [False, True]


async def test_f44_no_loop_even_without_from_bot_flag(bot):
    bot.repo.create({"name": "L", "trigger": "!loop", "response": "!loop"})
    await say(bot, "donstvbot", "!loop", user_id="1001")  # Kennung des Bot-Kontos
    assert bot.twitch.sent == []


async def test_f41_duplicate_message_id_is_dropped(bot):
    bot.repo.create({"name": "T", "trigger": "!t", "response": "x"})
    await say(bot, "A", "!t", message_id="m-1")
    await say(bot, "A", "!t", message_id="m-1")
    assert bot.twitch.sent == ["x"]
    assert len([e for e in bot.events if e.type == "twitch.chat.message" and e.payload["message_id"] == "m-1"]) == 1
    assert len(bot.engine.history) == 2  # Original und Echo des Bots, das Duplikat nicht


async def test_f41_chat_history_is_limited(bot):
    for i in range(CHAT_HISTORY + 20):
        await say(bot, "A", f"Nachricht {i}")
    assert len(bot.engine.history) == CHAT_HISTORY
    assert bot.engine.history[0]["text"] == "Nachricht 20"


# --- Ausführungs-Schnittstelle und F-45 -------------------------------------------------------------

async def test_f45_send_error_is_logged(bot):
    bot.repo.create({"name": "T", "trigger": "!t", "response": "x"})
    bot.twitch.fail_next = "Twitch ist nicht verbunden"
    await say(bot, "A", "!t")
    entry = bot.log.recent()[-1]
    assert entry["kind"] == botlog.SEND_ERROR and "nicht verbunden" in entry["message"]


async def test_executor_only_knows_chat_send(bot):
    ex = ActionExecutor(lambda: bot.twitch, bot.log)
    assert (await ex.run({"type": "chat.send", "text": "hi"}, {}))["message_id"]
    with pytest.raises(ActionError):
        await ex.run({"type": "obs.scene"}, {})


async def test_f45_log_is_stored_and_published(bot):
    await bot.log.add(botlog.CONNECTION, "Twitch: verbunden")
    published = [e for e in bot.events if e.type == "bot.log"]
    assert published[-1].payload["message"] == "Twitch: verbunden"
    assert bot.log.recent()[-1]["message"] == "Twitch: verbunden"
    # Status der Twitch-Verbindung landet im Protokoll
    await bot.twitch.set_status(bot.twitch.status.ERROR, "Netz weg")
    assert bot.log.recent()[-1]["kind"] == botlog.CONNECTION and "Netz weg" in bot.log.recent()[-1]["message"]


async def test_f45_log_redacts_tokens_and_is_bounded(tmp_path):
    bus, store = EventBus(), Store(tmp_path / "l.db")
    log = BotLog(store, bus, keep=3)
    await log.add(botlog.AUTH, "Fehler: access_token=geheim123", {"x": "Authorization: Bearer geheim456"})
    for i in range(5):
        await log.add(botlog.CONNECTION, f"Eintrag {i}")
    rows = store.query("SELECT message, data FROM bot_log")
    assert len(rows) == 3
    assert "geheim" not in repr(rows)
    log2 = BotLog(store, bus)
    await log2.add(botlog.AUTH, "access_token=geheim789", {"t": "oauth geheim000"})
    assert "geheim" not in repr(store.query("SELECT message, data FROM bot_log"))


def test_render_and_first_word():
    assert render("Hi {user} {user} {other}", {"display_name": "Zoë"}) == "Hi Zoë Zoë {other}"
    assert first_word("  !Regeln jetzt") == "!regeln"
    assert first_word("") == ""
