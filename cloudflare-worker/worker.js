const STOCK_KEY = "stock:latest";
const STOCK_HTML = `<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>股票模擬</title>
  <link rel="stylesheet" href="/stock.css">
</head>
<body>
  <div class="page">
    <header class="topbar">
      <h2 class="stock-title">鉤月證券所</h2>
      <button id="updateOnlyBtn" type="button">手動更新</button>
      <button id="broadcastBtn" type="button">僅廣播</button>
      <button id="updateBroadcastBtn" type="button">更新並廣播</button>
      <button id="testTickBtn" type="button">測試變動</button>
      <span id="stockStatus" class="status"></span>
    </header>
    <section class="stock-panel">
      <div class="history-head">
        <span>市場資訊</span>
        <span id="lastUpdated" class="status"></span>
      </div>
      <div class="stock-table-wrap">
        <table class="stock-table">
          <thead>
            <tr>
              <th>代號</th><th>名稱</th><th>現價</th><th>前收</th><th>漲跌</th><th>漲跌幅</th><th>更新時間 (UTC+8)</th>
            </tr>
          </thead>
          <tbody id="stockRows"></tbody>
        </table>
      </div>
    </section>
  </div>
  <script src="/stock.js"></script>
</body>
</html>`;

const STOCK_CSS = `
*{box-sizing:border-box}body{margin:0;font-family:"Segoe UI",Arial,sans-serif;background:#f6f7fb;color:#222}
.page{max-width:1600px;margin:0 auto;padding:16px}.topbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}
button{font-size:14px;padding:6px 8px}.status{color:#666;font-size:13px}.stock-title{margin:0;font-size:20px}
.stock-panel{border:1px solid #d9dce8;border-radius:8px;background:#fff;padding:10px}
.history-head{display:flex;align-items:center;justify-content:space-between;gap:8px;font-weight:700;margin-bottom:8px}
.stock-table-wrap{overflow:auto}.stock-table{width:100%;border-collapse:collapse}
.stock-table th,.stock-table td{border-bottom:1px solid #eceff8;text-align:left;padding:8px 6px;white-space:nowrap}
.stock-table .up{color:#0a8a42}.stock-table .down{color:#c92c2c}.stock-table .flat{color:#666}`;

const STOCK_JS = `
const ui={stockRows:document.getElementById("stockRows"),lastUpdated:document.getElementById("lastUpdated"),stockStatus:document.getElementById("stockStatus"),updateOnlyBtn:document.getElementById("updateOnlyBtn"),broadcastBtn:document.getElementById("broadcastBtn"),updateBroadcastBtn:document.getElementById("updateBroadcastBtn"),testTickBtn:document.getElementById("testTickBtn")};
function fmtSigned(v){const n=Number(v||0);return \`\${n>=0?"+":""}\${n.toFixed(2)}\`;}
function render(snapshot){const items=snapshot?.items||[];ui.stockRows.innerHTML="";for(const item of items){const tr=document.createElement("tr");const pct=fmtSigned(item.change_pct);const cls=Number(item.change||0)>0?"up":Number(item.change||0)<0?"down":"flat";tr.innerHTML=\`<td>\${item.symbol}</td><td>\${item.name}</td><td>\${Number(item.price).toFixed(2)}</td><td>\${Number(item.prev_close).toFixed(2)}</td><td class="\${cls}">\${fmtSigned(item.change)}</td><td class="\${cls}">\${pct}%</td><td>\${item.updated_at||""}</td>\`;ui.stockRows.appendChild(tr);}ui.lastUpdated.textContent=\`Tick #\${snapshot?.tick_count??0}\`;}
async function callApi(path,payload){const opt={method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload||{})};const res=await fetch(path,opt);const data=await res.json();if(!res.ok)throw new Error(data?.detail||data?.message||\`error \${res.status}\`);return data;}
async function refresh(){const res=await fetch("/stock/snapshot");const data=await res.json();if(!res.ok)throw new Error(data?.message||\`error \${res.status}\`);render(data);}
ui.updateOnlyBtn.addEventListener("click",async()=>{try{const data=await callApi("/stock/update",{});render(data.snapshot||data);ui.stockStatus.textContent=\`更新完成 \${new Date().toLocaleTimeString()}\`;}catch(e){ui.stockStatus.textContent=\`更新失敗: \${String(e.message||e)}\`;}});
ui.broadcastBtn.addEventListener("click",async()=>{try{const data=await callApi("/stock/broadcast",{});render(data.snapshot||data);ui.stockStatus.textContent=\`廣播完成 \${new Date().toLocaleTimeString()}\`;}catch(e){ui.stockStatus.textContent=\`廣播失敗: \${String(e.message||e)}\`;}});
ui.updateBroadcastBtn.addEventListener("click",async()=>{try{const data=await callApi("/stock/update-and-broadcast",{});render(data.snapshot||data);ui.stockStatus.textContent=\`更新並廣播完成 \${new Date().toLocaleTimeString()}\`;}catch(e){ui.stockStatus.textContent=\`更新失敗: \${String(e.message||e)}\`;}});
ui.testTickBtn.addEventListener("click",async()=>{try{const data=await callApi("/stock/test-tick",{});render(data.snapshot||data);ui.stockStatus.textContent=\`測試變動完成 \${new Date().toLocaleTimeString()}\`;}catch(e){ui.stockStatus.textContent=\`測試失敗: \${String(e.message||e)}\`;}});
refresh().catch(()=>{ui.stockStatus.textContent="同步失敗";});
`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "GET" && path === "/stock") {
      return new Response(STOCK_HTML, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }
    if (request.method === "GET" && path === "/stock.js") {
      return new Response(STOCK_JS, { headers: { "Content-Type": "application/javascript; charset=utf-8" } });
    }
    if (request.method === "GET" && path === "/stock.css") {
      return new Response(STOCK_CSS, { headers: { "Content-Type": "text/css; charset=utf-8" } });
    }
    if (request.method === "GET" && path === "/stock/snapshot") {
      const snapshot = await getOrInitSnapshot(env);
      return json(snapshot, 200);
    }
    if (request.method === "POST" && path === "/stock/update") {
      const snapshot = await getOrInitSnapshot(env);
      const updated = applyAutoTick(snapshot);
      await saveSnapshot(env, updated);
      return json({ ok: true, message: "Updated.", snapshot: updated }, 200);
    }
    if (request.method === "POST" && path === "/stock/test-tick") {
      const snapshot = await getOrInitSnapshot(env);
      const updated = applyAutoTick(snapshot);
      await saveSnapshot(env, updated);
      return json({ ok: true, message: "Test tick applied.", snapshot: updated }, 200);
    }
    if (request.method === "POST" && path === "/stock/broadcast") {
      const snapshot = await getOrInitSnapshot(env);
      const result = await broadcastSnapshot(env, snapshot);
      if (!result.ok) return json(result, 400);
      return json({ ok: true, message: "Broadcast sent.", snapshot }, 200);
    }
    if (request.method === "POST" && path === "/stock/update-and-broadcast") {
      const snapshot = await getOrInitSnapshot(env);
      const updated = applyAutoTick(snapshot);
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
