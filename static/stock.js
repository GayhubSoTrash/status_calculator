const ui = {
  stockRows: document.getElementById("stockRows"),
  lastUpdated: document.getElementById("lastUpdated"),
  stockStatus: document.getElementById("stockStatus"),
  manualTickBtn: document.getElementById("manualTickBtn"),
  manualBroadcastBtn: document.getElementById("manualBroadcastBtn"),
};

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
    tr.innerHTML = `
      <td>${item.symbol}</td>
      <td>${item.name}</td>
      <td>${Number(item.price).toFixed(2)}</td>
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

ui.manualTickBtn.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/stock/tick", { method: "POST" });
    if (!res.ok) throw new Error(`tick error: ${res.status}`);
    const data = await res.json();
    render(data);
    ui.stockStatus.textContent = `手動更新 ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    ui.stockStatus.textContent = "手動更新失敗";
  }
});

ui.manualBroadcastBtn.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/stock/broadcast-test", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.message || `broadcast error: ${res.status}`);
    ui.stockStatus.textContent = `廣播完成 ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    ui.stockStatus.textContent = "測試廣播失敗";
  }
});

refresh();
setInterval(refresh, 15000);
