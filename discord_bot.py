from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

try:
    import discord
except Exception:  # pragma: no cover - handled at runtime when dependency missing
    discord = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class DiscordBroadcaster:
    def __init__(
        self,
        token: str | None,
        channel_id: int | None,
        interval_sec: int,
        get_message_text,
    ) -> None:
        self.token = token
        self.channel_id = channel_id
        self.interval_sec = max(10, int(interval_sec))
        self.get_message_text = get_message_text
        self._ready = asyncio.Event()
        self._client: Any = None
        self._runner_task: asyncio.Task | None = None
        self._broadcast_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._runner_task and not self._runner_task.done():
            return
        if not self.token or not self.channel_id:
            logger.info("Discord broadcaster disabled: missing token/channel.")
            return
        if discord is None:
            logger.warning("Discord broadcaster disabled: discord.py not installed.")
            return

        intents = discord.Intents.none()
        intents.guilds = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready():
            logger.info("Discord bot connected as %s", self._client.user)
            self._ready.set()

        self._runner_task = asyncio.create_task(self._run_client(), name="discord-client-runner")

    async def stop(self) -> None:
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._broadcast_task
        self._broadcast_task = None
        if self._client is not None:
            await self._client.close()
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._runner_task
        self._runner_task = None
        self._ready.clear()

    async def _run_client(self) -> None:
        try:
            await self._client.start(self.token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Discord client stopped unexpectedly.")

    async def ensure_broadcast_loop(self) -> None:
        if not self._runner_task or self._runner_task.done():
            await self.start()
        if self._broadcast_task and not self._broadcast_task.done():
            return
        if not self._runner_task:
            return
        self._broadcast_task = asyncio.create_task(
            self._broadcast_loop(), name="discord-broadcast-loop"
        )

    async def broadcast_now(self) -> bool:
        """
        Trigger one immediate broadcast.
        Returns True when the send attempt is executed, False when broadcaster is disabled.
        """
        if not self._runner_task or self._runner_task.done():
            await self.start()
        if not self._runner_task:
            return False
        await self._ready.wait()
        await self._broadcast_once()
        return True

    async def _broadcast_loop(self) -> None:
        try:
            await self._ready.wait()
            while True:
                await asyncio.sleep(self.interval_sec)
                await self._broadcast_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Broadcast loop crashed.")

    async def _broadcast_once(self) -> None:
        if self._client is None:
            return
        chan = self._client.get_channel(self.channel_id)
        if chan is None:
            try:
                chan = await self._client.fetch_channel(self.channel_id)
            except Exception:
                logger.exception("Cannot fetch discord channel %s", self.channel_id)
                return
        try:
            await chan.send(self.get_message_text())
        except Exception:
            logger.exception("Failed to send stock broadcast message.")

