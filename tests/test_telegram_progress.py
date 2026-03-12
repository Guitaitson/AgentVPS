import asyncio
from types import SimpleNamespace

import pytest

import telegram_bot.bot as bot_module


class _DummyStatusMessage:
    def __init__(self, text):
        self.text = text
        self.edits = []
        self.deleted = False

    async def edit_text(self, text):
        self.text = text
        self.edits.append(text)

    async def delete(self):
        self.deleted = True


class _DummyMessage:
    def __init__(self):
        self.sent = []

    async def reply_text(self, text, *args, **kwargs):
        message = _DummyStatusMessage(text)
        self.sent.append(message)
        return message


class _DummyBot:
    def __init__(self):
        self.actions = []

    async def send_chat_action(self, chat_id, action):
        self.actions.append((chat_id, action))


@pytest.mark.asyncio
async def test_telegram_progress_session_shows_status_for_slow_requests(monkeypatch):
    monkeypatch.setattr(bot_module, "PROGRESS_MESSAGE_THRESHOLD_SECONDS", 0.0)
    monkeypatch.setattr(bot_module, "TYPING_INTERVAL_SECONDS", 999.0)

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        message=_DummyMessage(),
    )
    context = SimpleNamespace(bot=_DummyBot())

    session = bot_module.TelegramProgressSession(update, context)
    await session.start()
    await asyncio.sleep(0)
    await session.on_progress("external_call", {"server": "fleetintel"})
    await asyncio.sleep(0)

    assert context.bot.actions
    assert update.message.sent
    assert update.message.sent[0].edits[-1] == "Consultando FleetIntel..."

    await session.close()
    assert update.message.sent[0].deleted is True
