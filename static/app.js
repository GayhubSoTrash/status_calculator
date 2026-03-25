const socket = io();

const ui = {
  entities: document.getElementById("entities"),
  createBtn: document.getElementById("createBtn"),
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
};

function parseDiceRange(s) {
  const str = String(s || "").trim().toLowerCase();
  if (!str) return null;
  if (str.includes("d")) {
    const parts = str.split("d");
    if (parts.length !== 2) return null;
    const x = Number(parts[0]);
    const y = Number(parts[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y) || x <= 0 || y <= 0) return null;
    return { min: x * 1, max: x * y };
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

  const modal = document.createElement("div");
  modal.className = "modal";

  const title = document.createElement("div");
  title.className = "modal-title";
  const h = document.createElement("div");
  h.textContent = `攻擊：${entity.name}`;
  title.appendChild(h);
  const closeX = rowButton("關閉", () => overlay.remove());
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

  addField("武器傷害(weapon damage)", weaponDamage);
  addField("傷害加值(damage modifier)", damageModifier);
  addField("額外傷害(extra damage)", extraDamage);
  addField("額外混亂(extra stagger)", extraStagger);
  addField("傷害倍率(damage multiplier)", damageMultiplier);
  addField("混亂倍率(stagger multiplier)", staggerMultiplier);
  addField("固定傷害(fixed damage)", fixedDamage);
  addField("固定混亂(fixed stagger)", fixedStagger);

  const typeWrap = document.createElement("div");
  typeWrap.style.gridColumn = "1 / -1";
  typeWrap.className = "field";
  const typeLabel = document.createElement("label");
  typeLabel.textContent = "傷害類型(damage type)";
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
  critLabel.textContent = "暴擊(critical hit)";
  critLabel.style.marginRight = "14px";
  const dodge = document.createElement("input");
  dodge.type = "checkbox";
  const dodgeLabel = document.createElement("label");
  dodgeLabel.textContent = "迴避絕對失敗(dodge fumble)";
  dodgeLabel.style.marginRight = "14px";
  const black = document.createElement("input");
  black.type = "checkbox";
  const blackLabel = document.createElement("label");
  blackLabel.textContent = "黑傷(black damage)";

  toggles.appendChild(crit);
  toggles.appendChild(critLabel);
  toggles.appendChild(dodge);
  toggles.appendChild(dodgeLabel);
  toggles.appendChild(black);
  toggles.appendChild(blackLabel);

  form.appendChild(toggles);

  const preview = document.createElement("div");
  preview.className = "preview";
  preview.textContent = "預計傷害：\"0\"/\"0\"";

  function calcPreview() {
    const range = parseDiceRange(weaponDamage.value);
    if (!range) {
      preview.textContent = "預計傷害：\"?\"/\"?\"";
      return;
    }

    const dmgMod = Number(damageModifier.value || 0);
    const exD = Number(extraDamage.value || 0);
    const exS = Number(extraStagger.value || 0);
    const dmgMul = Number(damageMultiplier.value || 1);
    const stMul = Number(staggerMultiplier.value || 1);
    const fixD = Number(fixedDamage.value || 0);
    const fixS = Number(fixedStagger.value || 0);

    // Determine weaponUsed range based on toggles.
    let weaponMinUsed = range.min;
    let weaponMaxUsed = range.max;
    let dmgModUsed = dmgMod;

    if (crit.checked) {
      weaponMinUsed = range.max * 2;
      weaponMaxUsed = range.max * 2;
      dmgModUsed = dmgMod * 2;
    } else if (dodge.checked) {
      weaponMinUsed = range.min * 2;
      weaponMaxUsed = range.max * 2;
      dmgModUsed = dmgMod * 2;
    }

    // Resistances
    const res = entity.resistances || {};
    let baseDamageRes = 1.0;
    let baseStaggerRes = 1.0;
    if (damageType.value === "斬擊") {
      baseDamageRes = Number(res.slash_damage_res || 0);
      baseStaggerRes = Number(res.slash_stagger_res || 0);
    } else if (damageType.value === "突刺") {
      baseDamageRes = Number(res.piercing_damage_res || 0);
      baseStaggerRes = Number(res.piercing_stagger_res || 0);
    } else {
      baseDamageRes = Number(res.blunt_damage_res || 0);
      baseStaggerRes = Number(res.blunt_stagger_res || 0);
    }

    if (entity.is_staggered) {
      baseDamageRes = 2.0;
      baseStaggerRes = 2.0;
    }

    if (black.checked) {
      const meanRes = (baseDamageRes + baseStaggerRes) / 2.0;
      baseDamageRes = meanRes;
      baseStaggerRes = meanRes;
    }

    const minD =
      floor0((weaponMinUsed + dmgModUsed + exD) * dmgMul * baseDamageRes + fixD);
    const maxD =
      floor0((weaponMaxUsed + dmgModUsed + exD) * dmgMul * baseDamageRes + fixD);
    const minS =
      floor0((weaponMinUsed + dmgModUsed + exS) * stMul * baseStaggerRes + fixS);
    const maxS =
      floor0((weaponMaxUsed + dmgModUsed + exS) * stMul * baseStaggerRes + fixS);

    preview.textContent = `預計傷害：\"${minD}~${maxD}\"/\"${minS}~${maxS}\"`;
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
    overlay.remove();
  });
  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "取消";
  cancelBtn.addEventListener("click", () => overlay.remove());
  actions.appendChild(cancelBtn);
  actions.appendChild(confirmBtn);

  modal.appendChild(title);
  modal.appendChild(form);
  modal.appendChild(preview);
  modal.appendChild(actions);
  overlay.appendChild(modal);

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });

  document.body.appendChild(overlay);
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
  grant.appendChild(rowButton("下一幕賦予減益", () => emit("grant_next", { entityId: entity.id, choice: select.value })));
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
    a.textContent = `${labelText}:\"`;
    row.appendChild(a);

    const dmgInp = makeResInput(damageValue);
    resInputs[kDamage] = dmgInp;
    row.appendChild(dmgInp);

    const mid = document.createElement("span");
    mid.textContent = "\"/\"";
    row.appendChild(mid);

    const stInp = makeResInput(staggerValue);
    resInputs[kStagger] = stInp;
    row.appendChild(stInp);

    const b = document.createElement("span");
    b.textContent = '\"';
    row.appendChild(b);

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

  const pendingKeys = ["Tremor", "Tremor_Burn", "Burn", "Bleed", "Rupture", "Corrosion"];
  // Include UTH next-turn stacks.
  pendingKeys.push("UTH");
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

  const keys = ["Tremor", "Tremor_Burn", "Burn", "Bleed", "Rupture", "Corrosion", "UTH"];
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

  const hpMax = Number(window.prompt("HP最大值: (hp_max)", "100"));
  const hpCur = Number(window.prompt("HP當前值: (hp_current)", String(hpMax)));
  const mpMax = Number(window.prompt("MP最大值: (mp_max)", "100"));
  const mpCur = Number(window.prompt("MP當前值: (mp_current)", String(mpMax)));

  const slashDamageRes = Number(window.prompt("斬擊-傷害抗性: (slash_damage_res)", "1.0"));
  const slashStaggerRes = Number(window.prompt("斬擊-混亂抗性: (slash_stagger_res)", "1.0"));
  const piercingDamageRes = Number(window.prompt("突刺-傷害抗性: (piercing_damage_res)", "1.0"));
  const piercingStaggerRes = Number(window.prompt("突刺-混亂抗性: (piercing_stagger_res)", "1.0"));
  const bluntDamageRes = Number(window.prompt("打擊-傷害抗性: (blunt_damage_res)", "1.0"));
  const bluntStaggerRes = Number(window.prompt("打擊-混亂抗性: (blunt_stagger_res)", "1.0"));

  const nums = [hpMax, hpCur, mpMax, mpCur, slashDamageRes, slashStaggerRes, piercingDamageRes, piercingStaggerRes, bluntDamageRes, bluntStaggerRes];
  if (nums.some((v) => Number.isNaN(v))) {
    alert("輸入無效，請重新新增目標。");
    return;
  }

  emit("create_entity", {
    name,
    hp_current: hpCur,
    hp_max: hpMax,
    mp_current: mpCur,
    mp_max: mpMax,
    slash_damage_res: slashDamageRes,
    slash_stagger_res: slashStaggerRes,
    piercing_damage_res: piercingDamageRes,
    piercing_stagger_res: piercingStaggerRes,
    blunt_damage_res: bluntDamageRes,
    blunt_stagger_res: bluntStaggerRes,
  });
});

ui.turnEndBtn.addEventListener("click", () => {
  emit("turn_end", { turn: Number(ui.turnInput.value || 1) });
});

ui.turnInput.addEventListener("change", () => {
  emit("set_turn", { turn: Number(ui.turnInput.value || 1) });
});

ui.clearHistoryBtn.addEventListener("click", () => {
  emit("clear_history", {});
});

socket.on("state_updated", (state) => render(state));
socket.on("action_error", (payload) => alert(payload?.message || "操作失敗"));

emit("request_state", {});
