const ui = {
  stockRows: document.getElementById("stockRows"),
  lastUpdated: document.getElementById("lastUpdated"),
  stockStatus: document.getElementById("stockStatus"),
  manualUpdateOnlyBtn: document.getElementById("manualUpdateOnlyBtn"),
  manualBroadcastBtn: document.getElementById("manualBroadcastBtn"),
  manualUpdateBroadcastBtn: document.getElementById("manualUpdateBroadcastBtn"),
};
const priceInputs = new Map();

function fmtSigned(v) {
  const n = Number(v || 0);
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
}

function render(snapshot) {
  const items = snapshot?.items || [];
  ui.stockRows.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");
    const pct = fmtSigned(item.change_pct);
    const cls = Number(item.change || 0) > 0 ? "up" : Number(item.change || 0) < 0 ? "down" : "flat";
    tr.innerHTML = `<td>${item.symbol}</td><td>${item.name}</td>`;
    const priceTd = document.createElement("td");
    const inp = document.createElement("input");
    inp.type = "number";
    inp.step = "0.01";
    inp.min = "0.01";
    inp.value = Number(item.price).toFixed(2);
    inp.style.width = "100px";
    priceInputs.set(item.symbol, inp);
    priceTd.appendChild(inp);
    tr.appendChild(priceTd);
    tr.innerHTML += `
      <td>${Number(item.prev_close).toFixed(2)}</td>
      <td class="${cls}">${fmtSigned(item.change)}</td>
      <td class="${cls}">${pct}%</td>
      <td>${item.updated_at || ""}</td>
    `;
    ui.stockRows.appendChild(tr);
  }
  ui.lastUpdated.textContent = `Tick #${snapshot?.tick_count ?? 0}`;
}

async function fetchSnapshot() {
  const res = await fetch("/api/stock/snapshot", { method: "GET" });
  if (!res.ok) throw new Error(`snapshot error: ${res.status}`);
  return res.json();
}

async function refresh() {
  try {
    const data = await fetchSnapshot();
    render(data);
    ui.stockStatus.textContent = `已同步 ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    ui.stockStatus.textContent = "同步失敗";
  }
}

function collectPrices() {
  const prices = {};
  for (const [symbol, inp] of priceInputs.entries()) {
    const v = Number(inp.value);
    if (!Number.isFinite(v) || v <= 0) {
      throw new Error(`${symbol} 價格無效`);
    }
    prices[symbol] = v;
  }
  return prices;
}

ui.manualUpdateOnlyBtn.addEventListener("click", async () => {
  try {
    const prices = collectPrices();
    const res = await fetch("/api/stock/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prices }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || data?.message || `update error: ${res.status}`);
    render(data.snapshot || data);
    ui.stockStatus.textContent = `更新完成 ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    ui.stockStatus.textContent = `更新失敗: ${String(err.message || err)}`;
  }
});

ui.manualBroadcastBtn.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/stock/broadcast", {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || data?.message || `broadcast error: ${res.status}`);
    render(data.snapshot || data);
    ui.stockStatus.textContent = `廣播完成 ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    ui.stockStatus.textContent = `廣播失敗: ${String(err.message || err)}`;
  }
});

ui.manualUpdateBroadcastBtn.addEventListener("click", async () => {
  try {
    const prices = collectPrices();
    const endpoint = "/api/stock/update-and-broadcast";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prices }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || data?.message || `update error: ${res.status}`);
    render(data.snapshot || data);
    ui.stockStatus.textContent = `更新並廣播完成 ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    ui.stockStatus.textContent = `更新失敗: ${String(err.message || err)}`;
  }
});

refresh();
