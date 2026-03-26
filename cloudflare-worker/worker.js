const STOCK_KEY = "stock:latest";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "GET" && path === "/stock/snapshot") {
      const snapshot = await getOrInitSnapshot(env);
      return json(snapshot, 200);
    }

    const needsAuth =
      (request.method === "POST" && path === "/stock/update") ||
      (request.method === "POST" && path === "/stock/broadcast") ||
      (request.method === "POST" && path === "/stock/update-and-broadcast");
    if (needsAuth && !isAuthorized(request, env)) {
      return json({ ok: false, message: "Unauthorized." }, 401);
    }

    if (request.method === "POST" && path === "/stock/update") {
      const body = await parseJson(request);
      if (!body.ok) return json(body.payload, 400);
      const snapshot = await getOrInitSnapshot(env);
      const updated = applyManualPrices(snapshot, body.payload.prices);
      await saveSnapshot(env, updated);
      return json({ ok: true, message: "Updated.", snapshot: updated }, 200);
    }

    if (request.method === "POST" && path === "/stock/broadcast") {
      const snapshot = await getOrInitSnapshot(env);
      const result = await broadcastSnapshot(env, snapshot);
      if (!result.ok) return json(result, 400);
      return json({ ok: true, message: "Broadcast sent.", snapshot }, 200);
    }

    if (request.method === "POST" && path === "/stock/update-and-broadcast") {
      const body = await parseJson(request);
      if (!body.ok) return json(body.payload, 400);
      const snapshot = await getOrInitSnapshot(env);
      const updated = applyManualPrices(snapshot, body.payload.prices);
      await saveSnapshot(env, updated);
      const result = await broadcastSnapshot(env, updated);
      if (!result.ok) return json({ ...result, snapshot: updated }, 400);
      return json({ ok: true, message: "Broadcast sent.", snapshot: updated }, 200);
    }

    return json({ ok: false, message: "Not found." }, 404);
  },

  async scheduled(_event, env, _ctx) {
    const snapshot = await getOrInitSnapshot(env);
    const next = applyAutoTick(snapshot);
    await saveSnapshot(env, next);
    await broadcastSnapshot(env, next);
  },
};

function isAuthorized(request, env) {
  const relayKey = request.headers.get("X-Relay-Key") || "";
  return Boolean(env.RELAY_API_KEY && relayKey === env.RELAY_API_KEY);
}

async function parseJson(request) {
  try {
    const payload = await request.json();
    if (!payload || typeof payload !== "object") {
      return { ok: false, payload: { ok: false, message: "Invalid JSON object." } };
    }
    return { ok: true, payload };
  } catch {
    return { ok: false, payload: { ok: false, message: "Invalid JSON." } };
  }
}

async function getOrInitSnapshot(env) {
  const raw = await env.STOCK_KV.get(STOCK_KEY);
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {}
  }
  const now = nowIsoUtc8();
  const init = {
    tick_count: 0,
    updated_at: now,
    items: [
      { symbol: "TIME", name: "時間", price: 1.0, prev_close: 1.0, updated_at: now },
      { symbol: "LUCK", name: "氣運", price: 1.0, prev_close: 1.0, updated_at: now },
    ],
  };
  await saveSnapshot(env, init);
  return init;
}

async function saveSnapshot(env, snapshot) {
  await env.STOCK_KV.put(STOCK_KEY, JSON.stringify(snapshot));
}

function applyManualPrices(snapshot, pricesObj) {
  if (!pricesObj || typeof pricesObj !== "object") {
    throw new Error("prices must be an object");
  }
  const now = nowIsoUtc8();
  const items = snapshot.items.map((item) => {
    if (!(item.symbol in pricesObj)) return item;
    const next = Number(pricesObj[item.symbol]);
    if (!Number.isFinite(next) || next <= 0) return item;
    return {
      ...item,
      prev_close: round2(item.price),
      price: round2(Math.max(0.01, next)),
      updated_at: now,
    };
  });
  return toViewSnapshot({
    ...snapshot,
    tick_count: Number(snapshot.tick_count || 0) + 1,
    updated_at: now,
    items,
  });
}

function applyAutoTick(snapshot) {
  const now = nowIsoUtc8();
  const items = snapshot.items.map((item) => {
    const ratio = 0.9 + Math.random() * 0.2;
    const nextPrice = Math.max(0.01, Number(item.price || 0) * ratio);
    return {
      ...item,
      prev_close: round2(item.price),
      price: round2(nextPrice),
      updated_at: now,
    };
  });
  return toViewSnapshot({
    ...snapshot,
    tick_count: Number(snapshot.tick_count || 0) + 1,
    updated_at: now,
    items,
  });
}

async function broadcastSnapshot(env, snapshot) {
  if (!env.DISCORD_WEBHOOK_URL) {
    return { ok: false, message: "DISCORD_WEBHOOK_URL secret missing." };
  }
  const text = stockBroadcastText(snapshot);
  const resp = await fetch(env.DISCORD_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: text.slice(0, 2000) }),
  });
  if (resp.ok) return { ok: true, status: resp.status };
  return { ok: false, status: resp.status, message: (await resp.text()).slice(0, 300) };
}

function toViewSnapshot(snapshot) {
  const items = (snapshot.items || []).map((item) => {
    const price = Number(item.price || 0);
    const prev = Number(item.prev_close || 0);
    const change = price - prev;
    const change_pct = prev === 0 ? 0 : (change / prev) * 100;
    return {
      ...item,
      price: round2(price),
      prev_close: round2(prev),
      change: round2(change),
      change_pct: round2(change_pct),
    };
  });
  return {
    tick_count: Number(snapshot.tick_count || 0),
    updated_at: snapshot.updated_at || nowIsoUtc8(),
    items,
  };
}

function stockBroadcastText(snapshot) {
  const lines = ["[Stock Simulator] Market update"];
  for (const item of (snapshot.items || []).slice(0, 5)) {
    const sign = Number(item.change || 0) >= 0 ? "+" : "";
    lines.push(
      `${item.symbol} ${item.price} (${sign}${item.change}, ${sign}${item.change_pct}%)`
    );
  }
  return lines.join("\n");
}

function nowIsoUtc8() {
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const utc8 = new Date(utcMs + 8 * 3600000);
  return utc8.toISOString().replace("Z", "+08:00");
}

function round2(v) {
  return Math.round(Number(v) * 100) / 100;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
