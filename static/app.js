const socket = io();

const ui = {
  entities: document.getElementById("entities"),
  createBtn: document.getElementById("createBtn"),
  historyLog: document.getElementById("historyLog"),
  turnInput: document.getElementById("turnInput"),
  turnEndBtn: document.getElementById("turnEndBtn"),
  statusText: document.getElementById("statusText"),
};

let currentState = null;

const debuffLabels = {
  Tremor: "震顫",
  Tremor_Burn: "震顫-灼熱",
  Burn: "燒傷",
  Bleed: "出血",
  Rupture: "破裂",
  Corrosion: "腐蝕",
};

function rowButton(text, onClick) {
  const btn = document.createElement("button");
  btn.textContent = text;
  btn.addEventListener("click", onClick);
  return btn;
}

function emit(name, payload) {
  socket.emit(name, payload);
}

function renderDebuffControls(entity, key) {
  const v = entity.debuff[key];
  if (v <= 0) return null;
  const row = document.createElement("div");
  row.className = "line-row";

  const label = document.createElement("span");
  label.textContent = `${debuffLabels[key]}: ${v}`;
  row.appendChild(label);

  row.appendChild(rowButton("-", () => emit("change_debuff", { entityId: entity.id, debuffKey: key, delta: -1 })));
  row.appendChild(rowButton("+", () => emit("change_debuff", { entityId: entity.id, debuffKey: key, delta: 1 })));

  if (key === "Tremor") {
    row.appendChild(rowButton("振幅轉換", () => emit("conversion", { entityId: entity.id })));
    row.appendChild(rowButton("震顫引爆 (消耗)", () => emit("activate_debuff", { entityId: entity.id, debuffKey: "Tremor", consume: true })));
    row.appendChild(rowButton("震顫引爆 (不消耗)", () => emit("activate_debuff", { entityId: entity.id, debuffKey: "Tremor", consume: false })));
  } else if (key === "Tremor_Burn") {
    row.appendChild(rowButton("震顫引爆 (消耗)", () => emit("activate_debuff", { entityId: entity.id, debuffKey: "Tremor_Burn", consume: true })));
    row.appendChild(rowButton("震顫引爆 (不消耗)", () => emit("activate_debuff", { entityId: entity.id, debuffKey: "Tremor_Burn", consume: false })));
  } else if (key === "Burn") {
    row.appendChild(rowButton("觸發燒傷(消耗)", () => emit("activate_debuff", { entityId: entity.id, debuffKey: "Burn", consume: true })));
    row.appendChild(rowButton("觸發燒傷 (不消耗)", () => emit("activate_debuff", { entityId: entity.id, debuffKey: "Burn", consume: false })));
  } else {
    row.appendChild(rowButton(`觸發${debuffLabels[key]}`, () => emit("activate_debuff", { entityId: entity.id, debuffKey: key })));
  }
  return row;
}

function renderPendingControls(entity, key) {
  const v = entity.pending[key];
  if (v <= 0) return null;
  const row = document.createElement("div");
  row.className = "line-row";
  const label = document.createElement("span");
  label.textContent = `下一幕 ${debuffLabels[key]}: ${v}`;
  row.appendChild(label);
  row.appendChild(rowButton("-", () => emit("change_pending", { entityId: entity.id, debuffKey: key, delta: -1 })));
  row.appendChild(rowButton("+", () => emit("change_pending", { entityId: entity.id, debuffKey: key, delta: 1 })));
  return row;
}

function renderEntity(entity) {
  const panel = document.createElement("section");
  panel.className = "entity";

  const head = document.createElement("div");
  head.className = "entity-head";
  const name = document.createElement("strong");
  name.textContent = `名稱: ${entity.name}`;
  head.appendChild(name);
  const actions = document.createElement("div");
  actions.appendChild(rowButton("清除傷害/混亂", () => emit("clear_entity", { entityId: entity.id })));
  actions.appendChild(rowButton("刪除目標", () => emit("delete_entity", { entityId: entity.id })));
  head.appendChild(actions);
  panel.appendChild(head);

  const stats = document.createElement("div");
  stats.className = "stats";
  stats.innerHTML = `<span>傷害: ${entity.damage}</span><span>混亂: ${entity.stager}</span>`;
  panel.appendChild(stats);

  const grant = document.createElement("div");
  grant.className = "grant-row";
  const select = document.createElement("select");
  for (const option of currentState.debuff_options) {
    const o = document.createElement("option");
    o.value = option;
    o.textContent = option;
    if (option === entity.debuff_combo_choice) o.selected = true;
    select.appendChild(o);
  }
  select.addEventListener("change", () => emit("set_combo_choice", { entityId: entity.id, choice: select.value }));
  grant.appendChild(select);
  grant.appendChild(rowButton("賦予", () => emit("grant_now", { entityId: entity.id, choice: select.value })));
  grant.appendChild(rowButton("下一幕賦予減益", () => emit("grant_next", { entityId: entity.id, choice: select.value })));
  panel.appendChild(grant);

  const pendingKeys = ["Tremor", "Tremor_Burn", "Burn", "Bleed", "Rupture", "Corrosion"];
  const hasPending = pendingKeys.some((k) => entity.pending[k] > 0);
  if (hasPending) {
    const pendingTitle = document.createElement("div");
    pendingTitle.className = "pending-title";
    pendingTitle.textContent = "下一幕減益:";
    panel.appendChild(pendingTitle);
    for (const key of pendingKeys) {
      const row = renderPendingControls(entity, key);
      if (row) panel.appendChild(row);
    }
  }

  const keys = ["Tremor", "Tremor_Burn", "Burn", "Bleed", "Rupture", "Corrosion"];
  for (const key of keys) {
    const row = renderDebuffControls(entity, key);
    if (row) panel.appendChild(row);
  }

  return panel;
}

function render(state) {
  currentState = state;
  ui.turnInput.value = String(state.turn);
  ui.entities.innerHTML = "";
  for (const entity of state.entities) {
    ui.entities.appendChild(renderEntity(entity));
  }
  ui.historyLog.textContent = (state.history_logs || []).join("\n");
  ui.historyLog.scrollTop = ui.historyLog.scrollHeight;
  ui.statusText.textContent = `已同步 ${new Date().toLocaleTimeString()}`;
}

ui.createBtn.addEventListener("click", () => {
  const name = window.prompt("目標名稱:");
  if (!name) return;
  emit("create_entity", { name });
});

ui.turnEndBtn.addEventListener("click", () => {
  emit("turn_end", { turn: Number(ui.turnInput.value || 1) });
});

ui.turnInput.addEventListener("change", () => {
  emit("set_turn", { turn: Number(ui.turnInput.value || 1) });
});

socket.on("state_updated", (state) => render(state));
socket.on("action_error", (payload) => alert(payload?.message || "操作失敗"));

emit("request_state", {});
