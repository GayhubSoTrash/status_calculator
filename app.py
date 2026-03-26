import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import socketio

from game_state import GameState
from stock_state import StockState


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

fastapi_app = FastAPI(title="Debuff Calculator Socket.IO")
fastapi_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

state = GameState()
state_lock = asyncio.Lock()
stock_state = StockState()
stock_lock = asyncio.Lock()
_discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


@fastapi_app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@fastapi_app.head("/")
async def index_head() -> Response:
    # Explicit HEAD support for uptime checks.
    return Response(status_code=200)


@fastapi_app.get("/stock")
async def stock_page() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "stock.html"))


@fastapi_app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@fastapi_app.head("/health")
async def health_head() -> Response:
    return Response(status_code=200)


@fastapi_app.get("/api/stock/snapshot")
async def stock_snapshot() -> JSONResponse:
    async with stock_lock:
        return JSONResponse(stock_state.snapshot())


@fastapi_app.post("/api/stock/update")
async def stock_update(payload: dict[str, Any]) -> JSONResponse:
    raw_prices = payload.get("prices", {})
    if not isinstance(raw_prices, dict):
        return JSONResponse({"ok": False, "message": "prices must be an object."}, status_code=400)
    prices: dict[str, float] = {}
    for k, v in raw_prices.items():
        try:
            prices[str(k)] = float(v)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "message": f"invalid price: {k}"}, status_code=400)

    async with stock_lock:
        snapshot = stock_state.update_prices(prices)
    return JSONResponse({"ok": True, "message": "Updated.", "snapshot": snapshot})


@fastapi_app.post("/api/stock/broadcast")
async def stock_broadcast() -> JSONResponse:
    async with stock_lock:
        snapshot = stock_state.snapshot()
        text = _stock_broadcast_text(snapshot)
    ok, detail = await _send_discord_webhook(text)
    if not ok:
        return JSONResponse(
            {
                "ok": False,
                "message": "Discord webhook failed.",
                "detail": detail,
                "snapshot": snapshot,
            },
            status_code=400,
        )
    return JSONResponse({"ok": True, "message": "Broadcast sent.", "snapshot": snapshot})


@fastapi_app.post("/api/stock/update-and-broadcast")
async def stock_update_and_broadcast(payload: dict[str, Any]) -> JSONResponse:
    raw_prices = payload.get("prices", {})
    if not isinstance(raw_prices, dict):
        return JSONResponse({"ok": False, "message": "prices must be an object."}, status_code=400)
    prices: dict[str, float] = {}
    for k, v in raw_prices.items():
        try:
            prices[str(k)] = float(v)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "message": f"invalid price: {k}"}, status_code=400)

    async with stock_lock:
        snapshot = stock_state.update_prices(prices)
        text = _stock_broadcast_text(snapshot)
    ok, detail = await _send_discord_webhook(text)
    if not ok:
        return JSONResponse(
            {
                "ok": False,
                "message": "Discord webhook failed.",
                "detail": detail,
                "snapshot": snapshot,
            },
            status_code=400,
        )
    return JSONResponse({"ok": True, "message": "Broadcast sent.", "snapshot": snapshot})


async def emit_state() -> None:
    await sio.emit("state_updated", state.snapshot())


async def _send_discord_webhook(message: str) -> tuple[bool, str]:
    if not _discord_webhook_url:
        return False, "DISCORD_WEBHOOK_URL is empty."

    def _post() -> tuple[bool, str]:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urlrequest.Request(
            _discord_webhook_url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                status = int(resp.status)
                if 200 <= status < 300:
                    return True, f"HTTP {status}"
                return False, f"HTTP {status}"
        except urlerror.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = ""
            detail = f"HTTP {exc.code}"
            if body:
                detail += f" - {body[:300]}"
            return False, detail
        except urlerror.URLError as exc:
            return False, f"Network error: {exc.reason}"
        except TimeoutError:
            return False, "Request timeout."
        except Exception as exc:
            return False, f"Unexpected error: {exc}"

    return await asyncio.to_thread(_post)


def _stock_broadcast_text(snapshot: dict[str, Any]) -> str:
    items = snapshot.get("items", [])
    lines = ["[Stock Simulator] Market update"]
    for item in items[:5]:
        sign = "+" if item.get("change", 0) >= 0 else ""
        lines.append(
            f"{item.get('symbol')} {item.get('price')} ({sign}{item.get('change')}, {sign}{item.get('change_pct')}%)"
        )
    return "\n".join(lines)


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
            state.create_entity(
                str(payload.get("name", "")),
                int(payload.get("hp_current", 0)),
                int(payload.get("hp_max", 0)),
                int(payload.get("mp_current", 0)),
                int(payload.get("mp_max", 0)),
                float(payload.get("slash_damage_res", 0)),
                float(payload.get("slash_stagger_res", 0)),
                float(payload.get("piercing_damage_res", 0)),
                float(payload.get("piercing_stagger_res", 0)),
                float(payload.get("blunt_damage_res", 0)),
                float(payload.get("blunt_stagger_res", 0)),
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def delete_entity(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.record_undo_checkpoint("刪除目標")
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
            state.record_undo_checkpoint("觸發效果")
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
            state.record_undo_checkpoint("振幅轉換")
            state.conversion(_entity_id(payload))
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def turn_end(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.record_undo_checkpoint("幕結算")
            turn_value = payload.get("turn")
            state.turn_end(int(turn_value) if turn_value is not None else None)
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def clear_history(sid: str, payload: dict[str, Any] | None = None) -> None:
    try:
        async with state_lock:
            state.clear_history()
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def update_entity_stats(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.update_entity_stats(
                _entity_id(payload),
                int(payload.get("hp_current", 0)),
                int(payload.get("hp_max", 0)),
                int(payload.get("mp_current", 0)),
                int(payload.get("mp_max", 0)),
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def update_entity_resistances(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.update_entity_resistances(
                _entity_id(payload),
                float(payload.get("slash_damage_res", 0)),
                float(payload.get("slash_stagger_res", 0)),
                float(payload.get("piercing_damage_res", 0)),
                float(payload.get("piercing_stagger_res", 0)),
                float(payload.get("blunt_damage_res", 0)),
                float(payload.get("blunt_stagger_res", 0)),
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def attack_entity(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            state.record_undo_checkpoint("攻擊")
            state.attack_entity(
                _entity_id(payload),
                str(payload.get("weaponDamage", "0")),
                float(payload.get("damageModifier", 0)),
                float(payload.get("extraDamage", 0)),
                float(payload.get("extraStagger", 0)),
                float(payload.get("damageMultiplier", 1)),
                float(payload.get("staggerMultiplier", 1)),
                float(payload.get("fixedDamage", 0)),
                float(payload.get("fixedStagger", 0)),
                str(payload.get("damageType", "slash")),
                bool(payload.get("criticalHit", False)),
                bool(payload.get("dodgeFumble", False)),
                bool(payload.get("blackDamage", False)),
            )
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def undo(sid: str, payload: dict[str, Any] | None = None) -> None:
    try:
        async with state_lock:
            state.undo_last()
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def redo(sid: str, payload: dict[str, Any] | None = None) -> None:
    try:
        async with state_lock:
            state.redo_last()
            await emit_state()
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)


@sio.event
async def attack_preview(sid: str, payload: dict[str, Any]) -> None:
    try:
        async with state_lock:
            result = state.calculate_attack_preview(
                _entity_id(payload),
                str(payload.get("weaponDamage", "0")),
                float(payload.get("damageModifier", 0)),
                float(payload.get("extraDamage", 0)),
                float(payload.get("extraStagger", 0)),
                float(payload.get("damageMultiplier", 1)),
                float(payload.get("staggerMultiplier", 1)),
                float(payload.get("fixedDamage", 0)),
                float(payload.get("fixedStagger", 0)),
                str(payload.get("damageType", "slash")),
                bool(payload.get("criticalHit", False)),
                bool(payload.get("dodgeFumble", False)),
                bool(payload.get("blackDamage", False)),
            )
        await sio.emit(
            "attack_preview_result",
            {
                "entityId": _entity_id(payload),
                "requestId": payload.get("requestId"),
                **result,
            },
            room=sid,
        )
    except Exception as exc:
        await sio.emit("action_error", {"message": str(exc)}, room=sid)
