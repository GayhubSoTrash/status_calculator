from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class StockItem:
    symbol: str
    name: str
    price: float
    prev_close: float
    updated_at: str

    def as_dict(self) -> dict[str, Any]:
        change = self.price - self.prev_close
        pct = 0.0 if self.prev_close == 0 else (change / self.prev_close) * 100.0
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": round(self.price, 2),
            "prev_close": round(self.prev_close, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "updated_at": self.updated_at,
        }


class StockState:
    def __init__(self) -> None:
        now = self._now_iso()
        self._items: list[StockItem] = [
            StockItem("TIME", "時間", 1.0, 1.0, now),
            StockItem("LUCK", "氣運", 1.0, 1.0, now),
        ]
        self.tick_count = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self.tick_count,
            "updated_at": self._now_iso(),
            "items": [item.as_dict() for item in self._items],
        }

    def update_prices(self, prices: dict[str, float]) -> dict[str, Any]:
        now = self._now_iso()
        self.tick_count += 1
        for item in self._items:
            if item.symbol not in prices:
                continue
            next_price = max(0.01, float(prices[item.symbol]))
            item.prev_close = item.price
            item.price = round(next_price, 2)
            item.updated_at = now
        return self.snapshot()

    def _now_iso(self) -> str:
        tz_utc8 = timezone(timedelta(hours=8))
        return datetime.now(tz_utc8).isoformat(timespec="seconds")
