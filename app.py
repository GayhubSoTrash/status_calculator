import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import socketio

from game_state import GameState


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

fastapi_app = FastAPI(title="Debuff Calculator Socket.IO")
fastapi_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

state = GameState()
state_lock = asyncio.Lock()


@fastapi_app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


async def emit_state() -> None:
    await sio.emit("state_updated", state.snapshot())


def _entity_id(payload: dict[str, Any]) -> int:
    if "entityId" not in payload:
        raise ValueError("缺少 entityId。")
    return int(payload["entityId"])


@sio.event
async def connect(sid: str, environ: dict[str, Any]) -> None:
    await sio.emit("state_updated", state.snapshot(), room=sid)


@sio.event
async def request_state(sid: str) -> None:
    await sio.emit("state_updated", state.snapshot(), room=sid)


@sio.event
async def create_entity(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.create_entity(str(payload.get("name", "")))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def delete_entity(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.delete_entity(_entity_id(payload))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def clear_entity(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.clear_entity_damage_stager(_entity_id(payload))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def set_turn(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.set_turn(int(payload.get("turn", 0)))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def set_combo_choice(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.set_combo_choice(_entity_id(payload), str(payload.get("choice", "")))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def grant_now(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.grant_now(_entity_id(payload), str(payload.get("choice", "")))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def grant_next(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.grant_next(_entity_id(payload), str(payload.get("choice", "")))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def change_debuff(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.change_debuff(
                _entity_id(payload), str(payload.get("debuffKey", "")), int(payload.get("delta", 0))
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def change_pending(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.change_pending(
                _entity_id(payload), str(payload.get("debuffKey", "")), int(payload.get("delta", 0))
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def activate_debuff(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.activate(
                _entity_id(payload),
                str(payload.get("debuffKey", "")),
                bool(payload.get("consume", True)),
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def conversion(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.conversion(_entity_id(payload))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def turn_end(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            turn_value = payload.get("turn")
            state.turn_end(int(turn_value) if turn_value is not None else None)
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)
