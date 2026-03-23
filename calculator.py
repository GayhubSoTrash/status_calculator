import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import ttk
import math

DEBUFF_OPTIONS = ("震顫", "燒傷", "出血", "破裂", "腐蝕")


class debuff:
    def __init__(self):
        self.Tremor = 0
        self.Tremor_Burn = 0
        self.Burn = 0
        self.Bleed = 0   
        self.Rupture = 0
        self.Corrosion = 0


class entity:
    def __init__(self):
        self.name = ""
        self.damage = 0
        self.stager = 0
        self.debuff = debuff()
        self.pending = debuff()
        self.debuff_combo_choice = DEBUFF_OPTIONS[0]

def conversion(entity:entity): 
    entity.debuff.Tremor_Burn = entity.debuff.Tremor
    entity.debuff.Tremor=0

def tremor_burst(entity:entity, consume:bool):
    if(entity.debuff.Tremor_Burn > 0):
        before_stack = entity.debuff.Tremor_Burn
        entity.stager = entity.stager + entity.debuff.Tremor_Burn
        entity.damage = entity.damage + entity.debuff.Tremor_Burn
        burn_activation(entity, True)
        if(consume):
            entity.debuff.Tremor_Burn = entity.debuff.Tremor_Burn *2//3
        _record_activation(
            entity,
            "震顫-灼熱",
            damage_delta=before_stack,
            stager_delta=before_stack,
            stack_after=entity.debuff.Tremor_Burn,
        )
    elif (entity.debuff.Tremor > 0):
        before_stack = entity.debuff.Tremor
        entity.stager = entity.stager + entity.debuff.Tremor 
        if(consume):
            entity.debuff.Tremor = entity.debuff.Tremor *2//3
        _record_activation(
            entity,
            "震顫",
            stager_delta=before_stack,
            stack_after=entity.debuff.Tremor,
        )

def burn_activation(entity: entity, consume: bool = True):
    if entity.debuff.Burn > 0:
        before_stack = entity.debuff.Burn
        entity.damage = entity.damage + entity.debuff.Burn
        if consume:
            entity.debuff.Burn = entity.debuff.Burn * 2 // 3
        _record_activation(
            entity,
            "燒傷",
            damage_delta=before_stack,
            stack_after=entity.debuff.Burn,
        )

def bleed_activation(entity:entity):
    if(entity.debuff.Bleed > 0):
        before_stack = entity.debuff.Bleed
        entity.damage = entity.damage + entity.debuff.Bleed
        entity.debuff.Bleed = math.ceil(entity.debuff.Bleed *2/3)
        _record_activation(
            entity,
            "出血",
            damage_delta=before_stack,
            stack_after=entity.debuff.Bleed,
        )

def bleed_decay(entity:entity):
    if(entity.debuff.Bleed > 0):
        entity.debuff.Bleed = math.ceil(entity.debuff.Bleed *2/3)
        _record_settlement_decay(entity, "出血", entity.debuff.Bleed)

def rupture_activation(entity:entity):
    if(entity.debuff.Rupture > 0):
        before_stack = entity.debuff.Rupture
        entity.damage = entity.damage + entity.debuff.Rupture
        entity.debuff.Rupture = math.ceil(entity.debuff.Rupture *2/3)
        _record_activation(
            entity,
            "破裂",
            damage_delta=before_stack,
            stack_after=entity.debuff.Rupture,
        )

def rupture_decay(entity:entity):
    if(entity.debuff.Rupture > 0):
        entity.debuff.Rupture = math.ceil(entity.debuff.Rupture *2/3)
        _record_settlement_decay(entity, "破裂", entity.debuff.Rupture)

def corrosion_activation(entity: entity):
    if entity.debuff.Corrosion > 0:
        before_stack = entity.debuff.Corrosion
        entity.damage = entity.damage + entity.debuff.Corrosion
        entity.stager = entity.stager + entity.debuff.Corrosion
        _record_activation(
            entity,
            "腐蝕",
            damage_delta=before_stack,
            stager_delta=before_stack,
            stack_after=entity.debuff.Corrosion,
        )


def corrosion_decay(entity: entity):
    if entity.debuff.Corrosion > 0:
        entity.debuff.Corrosion = math.ceil(entity.debuff.Corrosion * 2 / 3)
        _record_settlement_decay(entity, "腐蝕", entity.debuff.Corrosion)


def _record_activation(
    ent: entity,
    debuff_name: str,
    damage_delta: int = 0,
    stager_delta: int = 0,
    stack_after: int = 0,
):
    if damage_delta <= 0 and stager_delta <= 0:
        return
    _append_history(
        f"\"{ent.name}\" 因 \"{debuff_name}\" 而受到 "
        f"\"{damage_delta}/{stager_delta}\" 點傷害，"
        f"層數降至\"{stack_after}\" 層，總計傷害為\"{ent.damage}/{ent.stager}\""
    )


def _record_settlement_decay(ent: entity, debuff_name: str, stack_after: int):
    _append_history(f"\"{ent.name}\" 的 \"{debuff_name}\" 因幕結算而降至\"{stack_after}\" 層")


def _record_next_turn_gain(ent: entity, debuff_name: str, gained_stack: int, total_stack: int):
    _append_history(
        f"\"{ent.name}\" 獲得 \"{gained_stack}\" 層 \"{debuff_name}\"，總計層數為\"{total_stack}\""
    )


def _apply_turn_end_for_entity(e: entity):
    burn_activation(e, True)
    tremor_burst(e, True)
    bleed_decay(e)
    rupture_decay(e)
    corrosion_decay(e)


def _inc_tremor_on_debuff(e: entity):
    if e.debuff.Tremor_Burn > 0:
        e.debuff.Tremor_Burn += 1
    else:
        e.debuff.Tremor += 1


def _inc_tremor_on_pending(e: entity):
    if e.pending.Tremor_Burn > 0 or e.debuff.Tremor_Burn > 0:
        e.pending.Tremor_Burn += 1
    else:
        e.pending.Tremor += 1


def _grant_debuff_by_choice(e: entity, choice: str):
    if choice == "震顫":
        _inc_tremor_on_debuff(e)
    elif choice == "燒傷":
        e.debuff.Burn += 1
    elif choice == "出血":
        e.debuff.Bleed += 1
    elif choice == "破裂":
        e.debuff.Rupture += 1
    elif choice == "腐蝕":
        e.debuff.Corrosion += 1


def _grant_pending_by_choice(e: entity, choice: str):
    if choice == "震顫":
        _inc_tremor_on_pending(e)
    elif choice == "燒傷":
        e.pending.Burn += 1
    elif choice == "出血":
        e.pending.Bleed += 1
    elif choice == "破裂":
        e.pending.Rupture += 1
    elif choice == "腐蝕":
        e.pending.Corrosion += 1


def _flush_pending_debuffs(e: entity):
    p = e.pending
    d = e.debuff
    if p.Burn > 0:
        d.Burn += p.Burn
        _record_next_turn_gain(e, "燒傷", p.Burn, d.Burn)
    if p.Bleed > 0:
        d.Bleed += p.Bleed
        _record_next_turn_gain(e, "出血", p.Bleed, d.Bleed)
    if p.Rupture > 0:
        d.Rupture += p.Rupture
        _record_next_turn_gain(e, "破裂", p.Rupture, d.Rupture)
    if p.Tremor > 0:
        d.Tremor += p.Tremor
        _record_next_turn_gain(e, "震顫", p.Tremor, d.Tremor)
    if p.Tremor_Burn > 0:
        d.Tremor_Burn += p.Tremor_Burn
        _record_next_turn_gain(e, "震顫-灼熱", p.Tremor_Burn, d.Tremor_Burn)
    if p.Corrosion > 0:
        d.Corrosion += p.Corrosion
        _record_next_turn_gain(e, "腐蝕", p.Corrosion, d.Corrosion)
    e.pending = debuff()


def _pending_any_nonzero(e: entity) -> bool:
    p = e.pending
    return (
        p.Tremor > 0
        or p.Tremor_Burn > 0
        or p.Burn > 0
        or p.Bleed > 0
        or p.Rupture > 0
        or p.Corrosion > 0
    )


# --------------------------
# Tkinter GUI implementation
# --------------------------
_entities = []  # type: list[entity]


def _non_negative(value: int) -> int:
    return value if value >= 0 else 0


def _normalize_combo_choice(value: str) -> str:
    return value if value in DEBUFF_OPTIONS else DEBUFF_OPTIONS[0]


_history_logs = []
_history_window = None
_history_text = None


def _append_history(text: str):
    global _history_logs, _history_text
    _history_logs.append(text)
    if _history_text is not None and _history_text.winfo_exists():
        _history_text.configure(state="normal")
        _history_text.insert("end", text + "\n")
        _history_text.see("end")
        _history_text.configure(state="disabled")


def _open_history_window(root: tk.Tk):
    global _history_window, _history_text
    if _history_window is not None and _history_window.winfo_exists():
        _history_window.lift()
        _history_window.focus_force()
        return

    _history_window = tk.Toplevel(root)
    _history_window.title("歷史記錄")
    _history_window.geometry("760x420")

    wrap = tk.Frame(_history_window, padx=10, pady=10)
    wrap.pack(fill="both", expand=True)

    scrollbar = tk.Scrollbar(wrap, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    _history_text = tk.Text(wrap, wrap="word", yscrollcommand=scrollbar.set)
    _history_text.pack(side="left", fill="both", expand=True)
    scrollbar.configure(command=_history_text.yview)

    if _history_logs:
        _history_text.insert("1.0", "\n".join(_history_logs) + "\n")
        _history_text.see("end")
    _history_text.configure(state="disabled")

    def _on_close_history():
        global _history_window, _history_text
        _history_window.destroy()
        _history_window = None
        _history_text = None

    _history_window.protocol("WM_DELETE_WINDOW", _on_close_history)


_current_turn = 1


def _render_all(root: tk.Tk, container: tk.Frame):
    # Clear container
    for child in list(container.children.values()):
        child.destroy()

    if not _entities:
        # Keep the container empty if there are no entities
        return

    # Render each entity as its own panel
    for idx, ent in enumerate(_entities):
        # Keep tremor states mutually exclusive in UI state.
        if ent.debuff.Tremor > 0 and ent.debuff.Tremor_Burn > 0:
            ent.debuff.Tremor_Burn += ent.debuff.Tremor
            ent.debuff.Tremor = 0
        if ent.pending.Tremor > 0 and ent.pending.Tremor_Burn > 0:
            ent.pending.Tremor_Burn += ent.pending.Tremor
            ent.pending.Tremor = 0

        panel = tk.Frame(container, bd=2, relief="groove", padx=8, pady=8)
        panel.pack(fill="x", pady=6)

        # Header: name (left) and entity actions (top right)
        header = tk.Frame(panel)
        header.pack(fill="x")
        tk.Label(header, text=f"名稱: {ent.name}", font=("Segoe UI", 11, "bold")).pack(side="left")

        def clear_entity(e=ent):
            e.damage = 0
            e.stager = 0
            _render_all(root, container)

        def delete_entity(e=ent):
            if e in _entities:
                _entities.remove(e)
            _render_all(root, container)

        hdr_actions = tk.Frame(header)
        hdr_actions.pack(side="right")
        tk.Button(hdr_actions, text="清除傷害/混亂", command=clear_entity).pack(side="left", padx=2)
        tk.Button(hdr_actions, text="刪除目標", command=delete_entity).pack(side="left", padx=2)

        # Stats: damage and stager
        stats = tk.Frame(panel)
        stats.pack(fill="x", pady=(4, 2))
        tk.Label(stats, text=f"傷害: {ent.damage}").pack(side="left", padx=(0, 12))
        tk.Label(stats, text=f"混亂: {ent.stager}").pack(side="left")

        # Single combobox: 賦予 (now) / 下一幕賦予減益 (pending)
        add_row = tk.Frame(panel)
        add_row.pack(fill="x", pady=(6, 2))
        combo_debuff = ttk.Combobox(
            add_row,
            values=DEBUFF_OPTIONS,
            state="readonly",
            width=10,
        )
        combo_debuff.set(_normalize_combo_choice(ent.debuff_combo_choice))
        combo_debuff.pack(side="left", padx=4)

        def on_debuff_combo_selected(e=ent, c=combo_debuff):
            e.debuff_combo_choice = _normalize_combo_choice(c.get())

        combo_debuff.bind(
            "<<ComboboxSelected>>",
            lambda _ev, e=ent, c=combo_debuff: on_debuff_combo_selected(e, c),
        )

        def do_grant_now(e=ent, c=combo_debuff):
            choice = _normalize_combo_choice(c.get() or e.debuff_combo_choice)
            e.debuff_combo_choice = choice
            _grant_debuff_by_choice(e, choice)
            _render_all(root, container)

        def do_grant_next(e=ent, c=combo_debuff):
            choice = _normalize_combo_choice(c.get() or e.debuff_combo_choice)
            e.debuff_combo_choice = choice
            _grant_pending_by_choice(e, choice)
            _render_all(root, container)

        tk.Button(add_row, text="賦予", command=lambda e=ent, c=combo_debuff: do_grant_now(e, c)).pack(
            side="left", padx=4
        )
        tk.Button(
            add_row,
            text="下一幕賦予減益",
            command=lambda e=ent, c=combo_debuff: do_grant_next(e, c),
        ).pack(side="left", padx=4)

        # Next-turn pending: edit with - / + (same idea as current debuff rows)
        if _pending_any_nonzero(ent):
            tk.Label(panel, text="下一幕減益:", font=("Segoe UI", 9, "bold")).pack(
                anchor="w", pady=(6, 2)
            )

        if ent.pending.Tremor > 0:
            pt_row = tk.Frame(panel)
            pt_row.pack(fill="x", pady=2)
            tk.Label(pt_row, text=f"下一幕 震顫: {ent.pending.Tremor}", fg="#555").pack(
                side="left"
            )

            def pt_tremor_dec(e=ent):
                e.pending.Tremor = _non_negative(e.pending.Tremor - 1)
                _render_all(root, container)

            def pt_tremor_inc(e=ent):
                _inc_tremor_on_pending(e)
                _render_all(root, container)

            tk.Button(pt_row, text="-", width=2, command=pt_tremor_dec).pack(side="left", padx=4)
            tk.Button(pt_row, text="+", width=2, command=pt_tremor_inc).pack(side="left", padx=2)

        if ent.pending.Tremor_Burn > 0:
            ptb_row = tk.Frame(panel)
            ptb_row.pack(fill="x", pady=2)
            tk.Label(ptb_row, text=f"下一幕 震顫-灼熱: {ent.pending.Tremor_Burn}", fg="#555").pack(
                side="left"
            )

            def pt_tmb_dec(e=ent):
                e.pending.Tremor_Burn = _non_negative(e.pending.Tremor_Burn - 1)
                _render_all(root, container)

            def pt_tmb_inc(e=ent):
                e.pending.Tremor_Burn += 1
                _render_all(root, container)

            tk.Button(ptb_row, text="-", width=2, command=pt_tmb_dec).pack(side="left", padx=4)
            tk.Button(ptb_row, text="+", width=2, command=pt_tmb_inc).pack(side="left", padx=2)

        if ent.pending.Burn > 0:
            pb_row = tk.Frame(panel)
            pb_row.pack(fill="x", pady=2)
            tk.Label(pb_row, text=f"下一幕 燒傷: {ent.pending.Burn}", fg="#555").pack(
                side="left"
            )

            def pb_dec(e=ent):
                e.pending.Burn = _non_negative(e.pending.Burn - 1)
                _render_all(root, container)

            def pb_inc(e=ent):
                e.pending.Burn += 1
                _render_all(root, container)

            tk.Button(pb_row, text="-", width=2, command=pb_dec).pack(side="left", padx=4)
            tk.Button(pb_row, text="+", width=2, command=pb_inc).pack(side="left", padx=2)

        if ent.pending.Bleed > 0:
            pbl_row = tk.Frame(panel)
            pbl_row.pack(fill="x", pady=2)
            tk.Label(pbl_row, text=f"下一幕 出血: {ent.pending.Bleed}", fg="#555").pack(
                side="left"
            )

            def pbl_dec(e=ent):
                e.pending.Bleed = _non_negative(e.pending.Bleed - 1)
                _render_all(root, container)

            def pbl_inc(e=ent):
                e.pending.Bleed += 1
                _render_all(root, container)

            tk.Button(pbl_row, text="-", width=2, command=pbl_dec).pack(side="left", padx=4)
            tk.Button(pbl_row, text="+", width=2, command=pbl_inc).pack(side="left", padx=2)

        if ent.pending.Rupture > 0:
            pr_row = tk.Frame(panel)
            pr_row.pack(fill="x", pady=2)
            tk.Label(pr_row, text=f"下一幕 破裂: {ent.pending.Rupture}", fg="#555").pack(
                side="left"
            )

            def pr_dec(e=ent):
                e.pending.Rupture = _non_negative(e.pending.Rupture - 1)
                _render_all(root, container)

            def pr_inc(e=ent):
                e.pending.Rupture += 1
                _render_all(root, container)

            tk.Button(pr_row, text="-", width=2, command=pr_dec).pack(side="left", padx=4)
            tk.Button(pr_row, text="+", width=2, command=pr_inc).pack(side="left", padx=2)

        if ent.pending.Corrosion > 0:
            pc_row = tk.Frame(panel)
            pc_row.pack(fill="x", pady=2)
            tk.Label(pc_row, text=f"下一幕 腐蝕: {ent.pending.Corrosion}", fg="#555").pack(
                side="left"
            )

            def pc_dec(e=ent):
                e.pending.Corrosion = _non_negative(e.pending.Corrosion - 1)
                _render_all(root, container)

            def pc_inc(e=ent):
                e.pending.Corrosion += 1
                _render_all(root, container)

            tk.Button(pc_row, text="-", width=2, command=pc_dec).pack(side="left", padx=4)
            tk.Button(pc_row, text="+", width=2, command=pc_inc).pack(side="left", padx=2)

        # Debuff sections: only show when value is non-zero
        # Tremor
        if ent.debuff.Tremor > 0:
            tremor_row = tk.Frame(panel)
            tremor_row.pack(fill="x", pady=2)
            tk.Label(tremor_row, text=f"震顫: {ent.debuff.Tremor}").pack(side="left")

            def tremor_dec(e=ent):
                e.debuff.Tremor = _non_negative(e.debuff.Tremor - 1)
                _render_all(root, container)

            def tremor_inc(e=ent):
                if e.debuff.Tremor_Burn > 0:
                    e.debuff.Tremor_Burn += 1
                else:
                    e.debuff.Tremor += 1
                _render_all(root, container)

            tk.Button(tremor_row, text="-", width=2, command=tremor_dec).pack(side="left", padx=4)
            tk.Button(tremor_row, text="+", width=2, command=tremor_inc).pack(side="left", padx=2)

            def do_conversion(e=ent):
                conversion(e)
                _render_all(root, container)

            def do_tremor_consume(e=ent):
                tremor_burst(e, True)
                _render_all(root, container)

            def do_tremor_no_consume(e=ent):
                tremor_burst(e, False)
                _render_all(root, container)

            # Conversion only appears when Tremor exists.
            tk.Button(tremor_row, text="振幅轉換", command=do_conversion).pack(side="left", padx=8)
            tk.Button(tremor_row, text="震顫引爆 (消耗)", command=do_tremor_consume).pack(side="left", padx=4)
            tk.Button(tremor_row, text="震顫引爆 (不消耗)", command=do_tremor_no_consume).pack(side="left", padx=4)

        # Tremor_Burn
        if ent.debuff.Tremor_Burn > 0:
            tmb_row = tk.Frame(panel)
            tmb_row.pack(fill="x", pady=2)
            tk.Label(tmb_row, text=f"震顫-灼熱: {ent.debuff.Tremor_Burn}").pack(side="left")

            def tmb_dec(e=ent):
                e.debuff.Tremor_Burn = _non_negative(e.debuff.Tremor_Burn - 1)
                _render_all(root, container)

            def tmb_inc(e=ent):
                e.debuff.Tremor_Burn += 1
                _render_all(root, container)

            tk.Button(tmb_row, text="-", width=2, command=tmb_dec).pack(side="left", padx=4)
            tk.Button(tmb_row, text="+", width=2, command=tmb_inc).pack(side="left", padx=2)

            def do_tremor_consume_from_tmb(e=ent):
                tremor_burst(e, True)
                _render_all(root, container)

            def do_tremor_no_consume_from_tmb(e=ent):
                tremor_burst(e, False)
                _render_all(root, container)

            # No conversion button here; Tremor_Burn cannot convert again.
            tk.Button(tmb_row, text="震顫引爆 (消耗)", command=do_tremor_consume_from_tmb).pack(side="left", padx=8)
            tk.Button(tmb_row, text="震顫引爆 (不消耗)", command=do_tremor_no_consume_from_tmb).pack(side="left", padx=4)

        # Burn
        if ent.debuff.Burn > 0:
            burn_row = tk.Frame(panel)
            burn_row.pack(fill="x", pady=2)
            tk.Label(burn_row, text=f"燒傷: {ent.debuff.Burn}").pack(side="left")

            def burn_dec(e=ent):
                e.debuff.Burn = _non_negative(e.debuff.Burn - 1)
                _render_all(root, container)

            def burn_inc(e=ent):
                e.debuff.Burn += 1
                _render_all(root, container)

            tk.Button(burn_row, text="-", width=2, command=burn_dec).pack(side="left", padx=4)
            tk.Button(burn_row, text="+", width=2, command=burn_inc).pack(side="left", padx=2)

            # Burn activation available when Burn > 0
            def burn_activate(e=ent):
                burn_activation(e, True)
                _render_all(root, container)

            def burn_activate_no_consume(e=ent):
                burn_activation(e, False)
                _render_all(root, container)

            tk.Button(burn_row, text="觸發燒傷(消耗)", command=burn_activate).pack(side="left", padx=8)
            tk.Button(burn_row, text="觸發燒傷 (不消耗)", command=burn_activate_no_consume).pack(side="left", padx=4)

        # Bleed (出血)
        if ent.debuff.Bleed > 0:
            bleed_row = tk.Frame(panel)
            bleed_row.pack(fill="x", pady=2)
            tk.Label(bleed_row, text=f"出血: {ent.debuff.Bleed}").pack(side="left")

            def bleed_dec(e=ent):
                e.debuff.Bleed = _non_negative(e.debuff.Bleed - 1)
                _render_all(root, container)

            def bleed_inc(e=ent):
                e.debuff.Bleed += 1
                _render_all(root, container)

            tk.Button(bleed_row, text="-", width=2, command=bleed_dec).pack(side="left", padx=4)
            tk.Button(bleed_row, text="+", width=2, command=bleed_inc).pack(side="left", padx=2)

            def bleed_activate(e=ent):
                bleed_activation(e)
                _render_all(root, container)

            tk.Button(bleed_row, text="觸發出血", command=bleed_activate).pack(side="left", padx=8)

        # Rupture (破裂)
        if ent.debuff.Rupture > 0:
            rupture_row = tk.Frame(panel)
            rupture_row.pack(fill="x", pady=2)
            tk.Label(rupture_row, text=f"破裂: {ent.debuff.Rupture}").pack(side="left")

            def rupture_dec(e=ent):
                e.debuff.Rupture = _non_negative(e.debuff.Rupture - 1)
                _render_all(root, container)

            def rupture_inc(e=ent):
                e.debuff.Rupture += 1
                _render_all(root, container)

            tk.Button(rupture_row, text="-", width=2, command=rupture_dec).pack(side="left", padx=4)
            tk.Button(rupture_row, text="+", width=2, command=rupture_inc).pack(side="left", padx=2)

            def rupture_activate(e=ent):
                rupture_activation(e)
                _render_all(root, container)

            tk.Button(rupture_row, text="觸發破裂", command=rupture_activate).pack(side="left", padx=8)

        # Corrosion (腐蝕): activation does not consume stack; decay at turn end only
        if ent.debuff.Corrosion > 0:
            corrosion_row = tk.Frame(panel)
            corrosion_row.pack(fill="x", pady=2)
            tk.Label(corrosion_row, text=f"腐蝕: {ent.debuff.Corrosion}").pack(side="left")

            def corrosion_dec(e=ent):
                e.debuff.Corrosion = _non_negative(e.debuff.Corrosion - 1)
                _render_all(root, container)

            def corrosion_inc(e=ent):
                e.debuff.Corrosion += 1
                _render_all(root, container)

            tk.Button(corrosion_row, text="-", width=2, command=corrosion_dec).pack(side="left", padx=4)
            tk.Button(corrosion_row, text="+", width=2, command=corrosion_inc).pack(side="left", padx=2)

            def corrosion_activate(e=ent):
                corrosion_activation(e)
                _render_all(root, container)

            tk.Button(corrosion_row, text="觸發腐蝕", command=corrosion_activate).pack(side="left", padx=8)

def _create_entity_flow(root: tk.Tk, container: tk.Frame):
    name = simpledialog.askstring("新增目標", "目標名稱:", parent=root)
    if name is None:
        return
    name = name.strip()
    if not name:
        messagebox.showwarning("無效的名稱", "目標名稱不能為空。")
        return
    ent = entity()
    ent.name = name
    _entities.append(ent)
    _render_all(root, container)


def main():
    global _current_turn
    root = tk.Tk()
    root.title("減益計算器")

    # Top-level layout: a centered Create button on first load; a container for entities
    top = tk.Frame(root, padx=12, pady=12)
    top.pack(fill="both", expand=True)

    # Top bar: create (left) and global turn end (right)
    btn_row = tk.Frame(top)
    btn_row.pack(fill="x", pady=(12, 12))
    # Entities container (scrollable)
    scroll_wrap = tk.Frame(top)
    scroll_wrap.pack(fill="both", expand=True)
    canvas = tk.Canvas(scroll_wrap, highlightthickness=0)
    vscroll = tk.Scrollbar(scroll_wrap, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    container = tk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")

    # Resize inner frame to canvas width and update scrollregion
    def _on_container_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    container.bind("<Configure>", _on_container_configure)

    def _on_canvas_configure(event):
        try:
            canvas.itemconfig(canvas_window, width=event.width)
        except Exception:
            pass
    canvas.bind("<Configure>", _on_canvas_configure)

    # Mouse wheel scrolling (Windows)
    def _on_mousewheel(event):
        try:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def on_create():
        _create_entity_flow(root, container)

    def on_turn_end_all():
        nonlocal turn_var
        global _current_turn
        try:
            parsed_turn = int(turn_var.get().strip())
            if parsed_turn <= 0:
                raise ValueError
            _current_turn = parsed_turn
        except Exception:
            turn_var.set(str(_current_turn))
            messagebox.showwarning("無效幕數", "幕數請輸入正整數。")
            return

        _append_history(f"-----第{_current_turn}幕結束結算-----")
        for e in _entities:
            _apply_turn_end_for_entity(e)
        _append_history(f"-------第{_current_turn + 1}幕開始-------")
        for e in _entities:
            _flush_pending_debuffs(e)
        _current_turn += 1
        turn_var.set(str(_current_turn))
        _render_all(root, container)

    def on_history():
        _open_history_window(root)

    create_btn = tk.Button(btn_row, text="新增目標", width=18, command=on_create)
    create_btn.pack(side="left")
    history_btn = tk.Button(btn_row, text="歷史記錄", width=14, command=on_history)
    history_btn.pack(side="left", padx=6)
    tk.Label(btn_row, text="幕數").pack(side="left", padx=(8, 4))
    turn_var = tk.StringVar(value=str(_current_turn))
    turn_entry = tk.Entry(btn_row, textvariable=turn_var, width=6)
    turn_entry.pack(side="left")
    turn_end_btn = tk.Button(btn_row, text="幕結束", width=14, command=on_turn_end_all)
    turn_end_btn.pack(side="left")

    # Initial render
    _render_all(root, container)

    # Center the window reasonably
    root.update_idletasks()
    try:
        # Place the window near the center of the screen
        w = 620
        h = 520
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 3)
        root.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
