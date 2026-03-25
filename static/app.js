const socket = io();

const ui = {
  entities: document.getElementById("entities"),
  createBtn: document.getElementById("createBtn"),
  undoBtn: document.getElementById("undoBtn"),
  Btredon: document.getElementById("redoBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
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
  UTH: "超高溫",
  Protection: "保護",
  StaggerProtection: "振奮",
  Vulnerable: "易損",
};

function parseDiceRange(s) {
  const str = String(s || "").trim().toLowerCase();
  if (!str) return null;
  const m = str.match(/^(\d+)\s*d\s*(\d+)\s*([+-]\s*\d+)?$/i);
  if (m) {
    const x = Number(m[1]);
    const y = Number(m[2]);
    const offset = m[3] ? Number(String(m[3]).replace(/\s+/g, "")) : 0;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(offset) || x <= 0 || y <= 0) {
      return null;
    }
    return { min: x * 1 + offset, max: x * y + offset };
  }
  const v = Number(str);
  if (!Number.isFinite(v) || v < 0) return null;
  return { min: v, max: v };
}

function floor0(n) {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.floor(n + 1e-9));
}

function openAttackModal(entity) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  let previewListenerBound = false;
  let onPreviewResult = null;
  function closeOverlay() {
    if (previewListenerBound && onPreviewResult) {
      socket.off("attack_preview_result", onPreviewResult);
      previewListenerBound = false;
    }
    overlay.remove();
  }

  const modal = document.createElement("div");
  modal.className = "modal";

  const title = document.createElement("div");
  title.className = "modal-title";
  const h = document.createElement("div");
  h.textContent = `攻擊：${entity.name}`;
  title.appendChild(h);
  const closeX = rowButton("關閉", () => closeOverlay());
  title.appendChild(closeX);

  const form = document.createElement("div");
  form.className = "grid2";

  const weaponDamage = document.createElement("input");
  weaponDamage.type = "text";
  weaponDamage.value = "1d1";

  const damageModifier = document.createElement("input");
  damageModifier.type = "number";
  damageModifier.value = "0";

  const extraDamage = document.createElement("input");
  extraDamage.type = "number";
  extraDamage.value = "0";

  const extraStagger = document.createElement("input");
  extraStagger.type = "number";
  extraStagger.value = "0";

  const damageMultiplier = document.createElement("input");
  damageMultiplier.type = "number";
  damageMultiplier.value = "1";

  const staggerMultiplier = document.createElement("input");
  staggerMultiplier.type = "number";
  staggerMultiplier.value = "1";

  const fixedDamage = document.createElement("input");
  fixedDamage.type = "number";
  fixedDamage.value = "0";

  const fixedStagger = document.createElement("input");
  fixedStagger.type = "number";
  fixedStagger.value = "0";

  function addField(labelText, inputEl) {
    const f = document.createElement("div");
    f.className = "field";
    const l = document.createElement("label");
    l.textContent = labelText;
    f.appendChild(l);
    f.appendChild(inputEl);
    form.appendChild(f);
  }

  addField("武器傷害", weaponDamage);
  addField("傷害加值", damageModifier);
  addField("額外傷害", extraDamage);
  addField("額外混亂", extraStagger);
  addField("傷害倍率", damageMultiplier);
  addField("混亂倍率", staggerMultiplier);
  addField("固定傷害", fixedDamage);
  addField("固定混亂", fixedStagger);

  const typeWrap = document.createElement("div");
  typeWrap.style.gridColumn = "1 / -1";
  typeWrap.className = "field";
  const typeLabel = document.createElement("label");
  typeLabel.textContent = "傷害類型";
  typeWrap.appendChild(typeLabel);

  const toggleRow = document.createElement("div");
  toggleRow.className = "toggle-row";

  const damageType = document.createElement("select");
  const optionSlash = document.createElement("option");
  optionSlash.value = "斬擊";
  optionSlash.textContent = "斬擊";
  const optionPiercing = document.createElement("option");
  optionPiercing.value = "突刺";
  optionPiercing.textContent = "突刺";
  const optionBlunt = document.createElement("option");
  optionBlunt.value = "打擊";
  optionBlunt.textContent = "打擊";
  damageType.appendChild(optionSlash);
  damageType.appendChild(optionPiercing);
  damageType.appendChild(optionBlunt);
  damageType.value = "斬擊";
  toggleRow.appendChild(damageType);
  typeWrap.appendChild(toggleRow);

  form.appendChild(typeWrap);

  const toggles = document.createElement("div");
  toggles.style.gridColumn = "1 / -1";
  toggles.className = "toggle-row";
  const crit = document.createElement("input");
  crit.type = "checkbox";
  const critLabel = document.createElement("label");
  critLabel.textContent = "暴擊";
  critLabel.style.marginRight = "14px";
  const dodge = document.createElement("input");
  dodge.type = "checkbox";
  const dodgeLabel = document.createElement("label");
  dodgeLabel.textContent = "迴避絕對失敗";
  dodgeLabel.style.marginRight = "14px";
  const black = document.createElement("input");
  black.type = "checkbox";
  const blackLabel = document.createElement("label");
  blackLabel.textContent = "黑傷";

  toggles.appendChild(crit);
  toggles.appendChild(critLabel);
  toggles.appendChild(dodge);
  toggles.appendChild(dodgeLabel);
  toggles.appendChild(black);
  toggles.appendChild(blackLabel);

  form.appendChild(toggles);

  const preview = document.createElement("div");
  preview.className = "preview";
  preview.textContent = "預計傷害：0/0";

  let previewRequestCounter = 0;
  const previewToken = `preview_${entity.id}_${Date.now()}_${Math.random()}`;
  overlay.dataset.previewToken = previewToken;

  function calcPreview() {
    const range = parseDiceRange(weaponDamage.value);
    if (!range) {
      preview.textContent = "預計傷害：?/?";
      return;
    }
    const requestId = `${previewToken}_${++previewRequestCounter}`;
    emit("attack_preview", {
      entityId: entity.id,
      requestId,
      weaponDamage: weaponDamage.value,
      damageModifier: Number(damageModifier.value || 0),
      extraDamage: Number(extraDamage.value || 0),
      extraStagger: Number(extraStagger.value || 0),
      damageMultiplier: Number(damageMultiplier.value || 1),
      staggerMultiplier: Number(staggerMultiplier.value || 1),
      fixedDamage: Number(fixedDamage.value || 0),
      fixedStagger: Number(fixedStagger.value || 0),
      damageType: damageType.value,
      criticalHit: crit.checked,
      dodgeFumble: dodge.checked,
      blackDamage: black.checked,
    });
  }

  const inputsToWatch = [
    weaponDamage,
    damageModifier,
    extraDamage,
    extraStagger,
    damageMultiplier,
    staggerMultiplier,
    fixedDamage,
    fixedStagger,
    damageType,
    crit,
    dodge,
    black,
  ];
  for (const el of inputsToWatch) {
    el.addEventListener("input", calcPreview);
    el.addEventListener("change", calcPreview);
  }
  calcPreview();

  const actions = document.createElement("div");
  actions.className = "modal-actions";
  const confirmBtn = document.createElement("button");
  confirmBtn.textContent = "確認";
  confirmBtn.addEventListener("click", () => {
    emit("attack_entity", {
      entityId: entity.id,
      weaponDamage: weaponDamage.value,
      damageModifier: Number(damageModifier.value || 0),
      extraDamage: Number(extraDamage.value || 0),
      extraStagger: Number(extraStagger.value || 0),
      damageMultiplier: Number(damageMultiplier.value || 1),
      staggerMultiplier: Number(staggerMultiplier.value || 1),
      fixedDamage: Number(fixedDamage.value || 0),
      fixedStagger: Number(fixedStagger.value || 0),
      damageType: damageType.value,
      criticalHit: crit.checked,
      dodgeFumble: dodge.checked,
      blackDamage: black.checked,
    });
  });
  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "取消";
  cancelBtn.addEventListener("click", () => closeOverlay());
  actions.appendChild(cancelBtn);
  actions.appendChild(confirmBtn);

  modal.appendChild(title);
  modal.appendChild(form);
  modal.appendChild(preview);
  modal.appendChild(actions);
  overlay.appendChild(modal);

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeOverlay();
  });

  document.body.appendChild(overlay);

  onPreviewResult = (result) => {
    if (!overlay.isConnected) {
      socket.off("attack_preview_result", onPreviewResult);
      return;
    }
    if (result.entityId !== entity.id) return;
    if (!String(result.requestId || "").startsWith(previewToken)) return;
    preview.textContent = `預計傷害：${result.min_damage}~${result.max_damage}/${result.min_stagger}~${result.max_stagger}`;
  };
  socket.on("attack_preview_result", onPreviewResult);
  previewListenerBound = true;
}

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
  } else if (key === "Protection" || key === "StaggerProtection" || key === "Vulnerable") {
    // Turn-based passive statuses: cannot be activated manually.
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
  actions.appendChild(rowButton("攻擊", () => openAttackModal(entity)));
  actions.appendChild(rowButton("刪除目標", () => emit("delete_entity", { entityId: entity.id })));
  head.appendChild(actions);
  panel.appendChild(head);

  const stats = document.createElement("div");
  stats.className = "stats";
  const makeNumInput = (value, step) => {
    const inp = document.createElement("input");
    inp.type = "number";
    inp.value = value;
    inp.step = step || "1";
    inp.style.width = "92px";
    return inp;
  };

  const hpLabel = document.createElement("span");
  hpLabel.textContent = "HP:";
  const hpCurInput = makeNumInput(entity.hp_current, "1");
  const hpSlash = document.createElement("span");
  hpSlash.textContent = "/";
  const hpMaxInput = makeNumInput(entity.hp_max, "1");

  const mpLabel = document.createElement("span");
  mpLabel.textContent = "MP:";
  const mpCurInput = makeNumInput(entity.mp_current, "1");
  const mpSlash = document.createElement("span");
  mpSlash.textContent = "/";
  const mpMaxInput = makeNumInput(entity.mp_max, "1");

  stats.appendChild(hpLabel);
  stats.appendChild(hpCurInput);
  stats.appendChild(hpSlash);
  stats.appendChild(hpMaxInput);
  stats.appendChild(mpLabel);
  stats.appendChild(mpCurInput);
  stats.appendChild(mpSlash);
  stats.appendChild(mpMaxInput);

  const syncStats = () => {
    const hpCur = Number(hpCurInput.value);
    const hpMax = Number(hpMaxInput.value);
    const mpCur = Number(mpCurInput.value);
    const mpMax = Number(mpMaxInput.value);
    if ([hpCur, hpMax, mpCur, mpMax].some((v) => Number.isNaN(v))) return;
    emit("update_entity_stats", {
      entityId: entity.id,
      hp_current: hpCur,
      hp_max: hpMax,
      mp_current: mpCur,
      mp_max: mpMax,
    });
  };

  hpCurInput.addEventListener("change", syncStats);
  hpMaxInput.addEventListener("change", syncStats);
  mpCurInput.addEventListener("change", syncStats);
  mpMaxInput.addEventListener("change", syncStats);

  panel.appendChild(stats);

  if (entity.is_staggered) {
    const s = document.createElement("div");
    s.className = "pending-title";
    s.textContent = `混亂狀態(回復於第${entity.stagger_recover_turn}幕結算)`;
    panel.appendChild(s);
  }

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
  grant.appendChild(rowButton("下一幕賦予", () => emit("grant_next", { entityId: entity.id, choice: select.value })));
  panel.appendChild(grant);

  // Resistances
  const res = entity.resistances || {};
  const resInputs = {};
  const makeResInput = (value) => makeNumInput(value, "0.1");

  function addResRow(labelText, damageValue, staggerValue, kDamage, kStagger) {
    const row = document.createElement("div");
    row.className = "line-row";
    row.style.marginTop = "6px";

    const a = document.createElement("span");
    a.textContent = `${labelText}:`;
    row.appendChild(a);

    const dmgInp = makeResInput(damageValue);
    resInputs[kDamage] = dmgInp;
    row.appendChild(dmgInp);

    const mid = document.createElement("span");
    mid.textContent = "/";
    row.appendChild(mid);

    const stInp = makeResInput(staggerValue);
    resInputs[kStagger] = stInp;
    row.appendChild(stInp);

    panel.appendChild(row);
  }

  addResRow(
    "斬擊",
    res.slash_damage_res,
    res.slash_stagger_res,
    "slash_damage_res",
    "slash_stagger_res",
  );
  addResRow(
    "突刺",
    res.piercing_damage_res,
    res.piercing_stagger_res,
    "piercing_damage_res",
    "piercing_stagger_res",
  );
  addResRow(
    "打擊",
    res.blunt_damage_res,
    res.blunt_stagger_res,
    "blunt_damage_res",
    "blunt_stagger_res",
  );

  const syncRes = () => {
    const payload = {
      entityId: entity.id,
      slash_damage_res: Number(resInputs.slash_damage_res.value),
      slash_stagger_res: Number(resInputs.slash_stagger_res.value),
      piercing_damage_res: Number(resInputs.piercing_damage_res.value),
      piercing_stagger_res: Number(resInputs.piercing_stagger_res.value),
      blunt_damage_res: Number(resInputs.blunt_damage_res.value),
      blunt_stagger_res: Number(resInputs.blunt_stagger_res.value),
    };
    if (Object.values(payload).slice(1).some((v) => Number.isNaN(v))) return;
    emit("update_entity_resistances", payload);
  };

  for (const inp of Object.values(resInputs)) {
    inp.addEventListener("change", syncRes);
  }

  const pendingKeys = [
    "Tremor",
    "Tremor_Burn",
    "Burn",
    "Bleed",
    "Rupture",
    "Corrosion",
    "UTH",
    "Protection",
    "StaggerProtection",
    "Vulnerable",
  ];
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

  const keys = [
    "Tremor",
    "Tremor_Burn",
    "Burn",
    "Bleed",
    "Rupture",
    "Corrosion",
    "UTH",
    "Protection",
    "StaggerProtection",
    "Vulnerable",
  ];
  for (const key of keys) {
    const row = renderDebuffControls(entity, key);
    if (row) panel.appendChild(row);
  }

  return panel;
}

function render(state) {
  currentState = state;
  ui.turnInput.value = String(state.turn);
  if (ui.undoBtn) ui.undoBtn.disabled = Number(state.undo_count || 0) <= 0;
  if (ui.redoBtn) ui.redoBtn.disabled = Number(state.redo_count || 0) <= 0;
  ui.entities.innerHTML = "";
  for (const entity of state.entities) {
    ui.entities.appendChild(renderEntity(entity));
  }
  ui.historyLog.textContent = (state.history_logs || []).join("\n");
  ui.historyLog.scrollTop = ui.historyLog.scrollHeight;
  ui.statusText.textContent = `已同步 ${new Date().toLocaleTimeString()}`;
}

ui.createBtn.addEventListener("click", () => {
  openCreateEntityModal();
});

function openCreateEntityModal() {
  function submitCreate() {
    const payload = {
      name: name.value.trim(),
      hp_max: Number(hpMax.value),
      hp_current: Number(hpCur.value),
      mp_max: Number(mpMax.value),
      mp_current: Number(mpCur.value),
      slash_damage_res: Number(slashDamageRes.value),
      slash_stagger_res: Number(slashStaggerRes.value),
      piercing_damage_res: Number(piercingDamageRes.value),
      piercing_stagger_res: Number(piercingStaggerRes.value),
      blunt_damage_res: Number(bluntDamageRes.value),
      blunt_stagger_res: Number(bluntStaggerRes.value),
    };
    const nums = [
      payload.hp_max,
      payload.hp_current,
      payload.mp_max,
      payload.mp_current,
      payload.slash_damage_res,
      payload.slash_stagger_res,
      payload.piercing_damage_res,
      payload.piercing_stagger_res,
      payload.blunt_damage_res,
      payload.blunt_stagger_res,
    ];
    if (!payload.name) {
      alert("請輸入目標名稱。");
      return;
    }
    if (nums.some((v) => Number.isNaN(v))) {
      alert("數值欄位有誤，請重新檢查。");
      return;
    }
    emit("create_entity", payload);
    overlay.remove();
  }

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  const modal = document.createElement("div");
  modal.className = "modal";

  const title = document.createElement("div");
  title.className = "modal-title";
  const titleText = document.createElement("div");
  titleText.textContent = "新增目標";
  title.appendChild(titleText);
  title.appendChild(rowButton("關閉", () => overlay.remove()));

  const form = document.createElement("div");
  form.className = "grid2";

  function makeField(label, value = "", type = "text", step = "1") {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const l = document.createElement("label");
    l.textContent = label;
    const inp = document.createElement("input");
    inp.type = type;
    inp.value = String(value);
    if (type === "number") inp.step = step;
    wrap.appendChild(l);
    wrap.appendChild(inp);
    form.appendChild(wrap);
    return inp;
  }

  const name = makeField("目標名稱", "", "text");
  const hpCur = makeField("HP當前值", 100, "number", "1");
  const hpMax = makeField("HP最大值", 100, "number", "1");
  const mpCur = makeField("MP當前值", 100, "number", "1");
  const mpMax = makeField("MP最大值", 100, "number", "1");
  const slashDamageRes = makeField("斬擊-傷害抗性", 1.0, "number", "0.1");
  const slashStaggerRes = makeField("斬擊-混亂抗性", 1.0, "number", "0.1");
  const piercingDamageRes = makeField("突刺-傷害抗性", 1.0, "number", "0.1");
  const piercingStaggerRes = makeField("突刺-混亂抗性", 1.0, "number", "0.1");
  const bluntDamageRes = makeField("打擊-傷害抗性", 1.0, "number", "0.1");
  const bluntStaggerRes = makeField("打擊-混亂抗性", 1.0, "number", "0.1");

  const actions = document.createElement("div");
  actions.className = "modal-actions";
  const cancel = rowButton("取消", () => overlay.remove());
  const confirm = rowButton("建立", () => submitCreate());
  actions.appendChild(cancel);
  actions.appendChild(confirm);

  modal.appendChild(title);
  modal.appendChild(form);
  modal.appendChild(actions);
  overlay.appendChild(modal);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  overlay.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitCreate();
    }
  });
  document.body.appendChild(overlay);
  name.focus();
}

ui.turnEndBtn.addEventListener("click", () => {
  emit("turn_end", { turn: Number(ui.turnInput.value || 1) });
});

ui.turnInput.addEventListener("change", () => {
  emit("set_turn", { turn: Number(ui.turnInput.value || 1) });
});

if (ui.undoBtn) {
  ui.undoBtn.addEventListener("click", () => emit("undo", {}));
}
if (ui.redoBtn) {
  ui.redoBtn.addEventListener("click", () => emit("redo", {}));
}

ui.clearHistoryBtn.addEventListener("click", () => {
  emit("clear_history", {});
});

socket.on("state_updated", (state) => render(state));
socket.on("action_error", (payload) => alert(payload?.message || "操作失敗"));

emit("request_state", {});
