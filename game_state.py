from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


DEBUFF_OPTIONS = ("震顫", "燒傷", "出血", "破裂", "腐蝕")


@dataclass
class Debuff:
    Tremor: int = 0
    Tremor_Burn: int = 0
    Burn: int = 0
    Bleed: int = 0
    Rupture: int = 0
    Corrosion: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "Tremor": self.Tremor,
            "Tremor_Burn": self.Tremor_Burn,
            "Burn": self.Burn,
            "Bleed": self.Bleed,
            "Rupture": self.Rupture,
            "Corrosion": self.Corrosion,
        }


@dataclass
class Entity:
    id: int
    name: str
    damage: int = 0
    stager: int = 0
    debuff: Debuff = field(default_factory=Debuff)
    pending: Debuff = field(default_factory=Debuff)
    debuff_combo_choice: str = DEBUFF_OPTIONS[0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "damage": self.damage,
            "stager": self.stager,
            "debuff": self.debuff.as_dict(),
            "pending": self.pending.as_dict(),
            "debuff_combo_choice": self.debuff_combo_choice,
        }


class GameState:
    def __init__(self) -> None:
        self.entities: list[Entity] = []
        self.history_logs: list[str] = []
        self.current_turn: int = 1
        self._next_id: int = 1

    def snapshot(self) -> dict[str, Any]:
        self._normalize_tremor_pairs()
        return {
            "turn": self.current_turn,
            "entities": [e.as_dict() for e in self.entities],
            "history_logs": self.history_logs,
            "debuff_options": DEBUFF_OPTIONS,
        }

    def create_entity(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("目標名稱不能為空。")
        ent = Entity(id=self._next_id, name=name)
        self._next_id += 1
        self.entities.append(ent)

    def delete_entity(self, entity_id: int) -> None:
        self.entities = [e for e in self.entities if e.id != entity_id]

    def clear_entity_damage_stager(self, entity_id: int) -> None:
        ent = self._get_entity(entity_id)
        ent.damage = 0
        ent.stager = 0

    def set_turn(self, turn: int) -> None:
        if turn <= 0:
            raise ValueError("幕數請輸入正整數。")
        self.current_turn = turn

    def clear_history(self) -> None:
        self.history_logs.clear()

    def set_combo_choice(self, entity_id: int, choice: str) -> None:
        ent = self._get_entity(entity_id)
        ent.debuff_combo_choice = self._normalize_choice(choice)

    def grant_now(self, entity_id: int, choice: str | None = None) -> None:
        ent = self._get_entity(entity_id)
        selected = self._normalize_choice(choice or ent.debuff_combo_choice)
        ent.debuff_combo_choice = selected
        self._grant_debuff_by_choice(ent, selected)
        self._normalize_tremor_pairs()

    def grant_next(self, entity_id: int, choice: str | None = None) -> None:
        ent = self._get_entity(entity_id)
        selected = self._normalize_choice(choice or ent.debuff_combo_choice)
        ent.debuff_combo_choice = selected
        self._grant_pending_by_choice(ent, selected)
        self._normalize_tremor_pairs()

    def change_debuff(self, entity_id: int, debuff_key: str, delta: int) -> None:
        ent = self._get_entity(entity_id)
        target = ent.debuff
        self._change_stack(target, debuff_key, delta, for_pending=False, ent=ent)
        self._normalize_tremor_pairs()

    def change_pending(self, entity_id: int, debuff_key: str, delta: int) -> None:
        ent = self._get_entity(entity_id)
        target = ent.pending
        self._change_stack(target, debuff_key, delta, for_pending=True, ent=ent)
        self._normalize_tremor_pairs()

    def activate(self, entity_id: int, debuff_key: str, consume: bool = True) -> None:
        ent = self._get_entity(entity_id)
        if debuff_key == "Tremor":
            self._tremor_burst(ent, consume)
        elif debuff_key == "Tremor_Burn":
            self._tremor_burst(ent, consume)
        elif debuff_key == "Burn":
            self._burn_activation(ent, consume)
        elif debuff_key == "Bleed":
            self._bleed_activation(ent)
        elif debuff_key == "Rupture":
            self._rupture_activation(ent)
        elif debuff_key == "Corrosion":
            self._corrosion_activation(ent)
        else:
            raise ValueError("未知減益。")
        self._normalize_tremor_pairs()

    def conversion(self, entity_id: int) -> None:
        ent = self._get_entity(entity_id)
        ent.debuff.Tremor_Burn = ent.debuff.Tremor
        ent.debuff.Tremor = 0

    def turn_end(self, turn_value: int | None = None) -> None:
        if turn_value is not None:
            self.set_turn(turn_value)
        self._append_history(f"-----第{self.current_turn}幕結束結算-----")
        for ent in self.entities:
            self._apply_turn_end_for_entity(ent)
        self._append_history(f"-------第{self.current_turn + 1}幕開始-------")
        for ent in self.entities:
            self._flush_pending_debuffs(ent)
        self.current_turn += 1
        self._normalize_tremor_pairs()

    def _change_stack(
        self, target: Debuff, debuff_key: str, delta: int, for_pending: bool, ent: Entity
    ) -> None:
        if debuff_key == "Tremor":
            if delta > 0:
                if for_pending:
                    self._inc_tremor_on_pending(ent)
                else:
                    self._inc_tremor_on_debuff(ent)
            else:
                target.Tremor = max(0, target.Tremor + delta)
            return
        if debuff_key not in {"Tremor_Burn", "Burn", "Bleed", "Rupture", "Corrosion"}:
            raise ValueError("未知減益。")
        current = getattr(target, debuff_key)
        setattr(target, debuff_key, max(0, current + delta))

    def _normalize_choice(self, choice: str) -> str:
        return choice if choice in DEBUFF_OPTIONS else DEBUFF_OPTIONS[0]

    def _get_entity(self, entity_id: int) -> Entity:
        for ent in self.entities:
            if ent.id == entity_id:
                return ent
        raise ValueError("找不到目標。")

    def _append_history(self, text: str) -> None:
        self.history_logs.append(text)

    def _record_activation(
        self,
        ent: Entity,
        debuff_name: str,
        damage_delta: int = 0,
        stager_delta: int = 0,
        stack_after: int = 0,
    ) -> None:
        if damage_delta <= 0 and stager_delta <= 0:
            return
        self._append_history(
            f"\"{ent.name}\" 因 \"{debuff_name}\" 而受到 "
            f"\"{damage_delta}/{stager_delta}\" 點傷害，"
            f"層數降至\"{stack_after}\" 層，總計傷害為\"{ent.damage}/{ent.stager}\""
        )

    def _record_settlement_decay(self, ent: Entity, debuff_name: str, stack_after: int) -> None:
        self._append_history(f"\"{ent.name}\" 的 \"{debuff_name}\" 因幕結算而降至\"{stack_after}\" 層")

    def _record_next_turn_gain(
        self, ent: Entity, debuff_name: str, gained_stack: int, total_stack: int
    ) -> None:
        self._append_history(
            f"\"{ent.name}\" 獲得 \"{gained_stack}\" 層 \"{debuff_name}\"，總計層數為\"{total_stack}\""
        )

    def _inc_tremor_on_debuff(self, ent: Entity) -> None:
        if ent.debuff.Tremor_Burn > 0:
            ent.debuff.Tremor_Burn += 1
        else:
            ent.debuff.Tremor += 1

    def _inc_tremor_on_pending(self, ent: Entity) -> None:
        if ent.pending.Tremor_Burn > 0 or ent.debuff.Tremor_Burn > 0:
            ent.pending.Tremor_Burn += 1
        else:
            ent.pending.Tremor += 1

    def _grant_debuff_by_choice(self, ent: Entity, choice: str) -> None:
        if choice == "震顫":
            self._inc_tremor_on_debuff(ent)
        elif choice == "燒傷":
            ent.debuff.Burn += 1
        elif choice == "出血":
            ent.debuff.Bleed += 1
        elif choice == "破裂":
            ent.debuff.Rupture += 1
        elif choice == "腐蝕":
            ent.debuff.Corrosion += 1

    def _grant_pending_by_choice(self, ent: Entity, choice: str) -> None:
        if choice == "震顫":
            self._inc_tremor_on_pending(ent)
        elif choice == "燒傷":
            ent.pending.Burn += 1
        elif choice == "出血":
            ent.pending.Bleed += 1
        elif choice == "破裂":
            ent.pending.Rupture += 1
        elif choice == "腐蝕":
            ent.pending.Corrosion += 1

    def _burn_activation(self, ent: Entity, consume: bool = True) -> None:
        if ent.debuff.Burn > 0:
            before_stack = ent.debuff.Burn
            ent.damage += ent.debuff.Burn
            if consume:
                ent.debuff.Burn = ent.debuff.Burn * 2 // 3
            self._record_activation(
                ent, "燒傷", damage_delta=before_stack, stack_after=ent.debuff.Burn
            )

    def _bleed_activation(self, ent: Entity) -> None:
        if ent.debuff.Bleed > 0:
            before_stack = ent.debuff.Bleed
            ent.damage += ent.debuff.Bleed
            ent.debuff.Bleed = math.ceil(ent.debuff.Bleed * 2 / 3)
            self._record_activation(
                ent, "出血", damage_delta=before_stack, stack_after=ent.debuff.Bleed
            )

    def _bleed_decay(self, ent: Entity) -> None:
        if ent.debuff.Bleed > 0:
            ent.debuff.Bleed = math.ceil(ent.debuff.Bleed * 2 / 3)
            self._record_settlement_decay(ent, "出血", ent.debuff.Bleed)

    def _rupture_activation(self, ent: Entity) -> None:
        if ent.debuff.Rupture > 0:
            before_stack = ent.debuff.Rupture
            ent.damage += ent.debuff.Rupture
            ent.debuff.Rupture = math.ceil(ent.debuff.Rupture * 2 / 3)
            self._record_activation(
                ent, "破裂", damage_delta=before_stack, stack_after=ent.debuff.Rupture
            )

    def _rupture_decay(self, ent: Entity) -> None:
        if ent.debuff.Rupture > 0:
            ent.debuff.Rupture = math.ceil(ent.debuff.Rupture * 2 / 3)
            self._record_settlement_decay(ent, "破裂", ent.debuff.Rupture)

    def _corrosion_activation(self, ent: Entity) -> None:
        if ent.debuff.Corrosion > 0:
            before_stack = ent.debuff.Corrosion
            ent.damage += ent.debuff.Corrosion
            ent.stager += ent.debuff.Corrosion
            self._record_activation(
                ent,
                "腐蝕",
                damage_delta=before_stack,
                stager_delta=before_stack,
                stack_after=ent.debuff.Corrosion,
            )

    def _corrosion_decay(self, ent: Entity) -> None:
        if ent.debuff.Corrosion > 0:
            ent.debuff.Corrosion = math.ceil(ent.debuff.Corrosion * 2 / 3)
            self._record_settlement_decay(ent, "腐蝕", ent.debuff.Corrosion)

    def _tremor_burst(self, ent: Entity, consume: bool) -> None:
        if ent.debuff.Tremor_Burn > 0:
            before_stack = ent.debuff.Tremor_Burn
            ent.stager += ent.debuff.Tremor_Burn
            ent.damage += ent.debuff.Tremor_Burn
            self._burn_activation(ent, True)
            if consume:
                ent.debuff.Tremor_Burn = ent.debuff.Tremor_Burn * 2 // 3
            self._record_activation(
                ent,
                "震顫-灼熱",
                damage_delta=before_stack,
                stager_delta=before_stack,
                stack_after=ent.debuff.Tremor_Burn,
            )
        elif ent.debuff.Tremor > 0:
            before_stack = ent.debuff.Tremor
            ent.stager += ent.debuff.Tremor
            if consume:
                ent.debuff.Tremor = ent.debuff.Tremor * 2 // 3
            self._record_activation(
                ent, "震顫", stager_delta=before_stack, stack_after=ent.debuff.Tremor
            )

    def _flush_pending_debuffs(self, ent: Entity) -> None:
        p = ent.pending
        d = ent.debuff
        if p.Burn > 0:
            d.Burn += p.Burn
            self._record_next_turn_gain(ent, "燒傷", p.Burn, d.Burn)
        if p.Bleed > 0:
            d.Bleed += p.Bleed
            self._record_next_turn_gain(ent, "出血", p.Bleed, d.Bleed)
        if p.Rupture > 0:
            d.Rupture += p.Rupture
            self._record_next_turn_gain(ent, "破裂", p.Rupture, d.Rupture)
        if p.Tremor > 0:
            d.Tremor += p.Tremor
            self._record_next_turn_gain(ent, "震顫", p.Tremor, d.Tremor)
        if p.Tremor_Burn > 0:
            d.Tremor_Burn += p.Tremor_Burn
            self._record_next_turn_gain(ent, "震顫-灼熱", p.Tremor_Burn, d.Tremor_Burn)
        if p.Corrosion > 0:
            d.Corrosion += p.Corrosion
            self._record_next_turn_gain(ent, "腐蝕", p.Corrosion, d.Corrosion)
        ent.pending = Debuff()

    def _apply_turn_end_for_entity(self, ent: Entity) -> None:
        self._burn_activation(ent, True)
        self._tremor_burst(ent, True)
        self._bleed_decay(ent)
        self._rupture_decay(ent)
        self._corrosion_decay(ent)

    def _normalize_tremor_pairs(self) -> None:
        for ent in self.entities:
            if ent.debuff.Tremor > 0 and ent.debuff.Tremor_Burn > 0:
                ent.debuff.Tremor_Burn += ent.debuff.Tremor
                ent.debuff.Tremor = 0
            if ent.pending.Tremor > 0 and ent.pending.Tremor_Burn > 0:
                ent.pending.Tremor_Burn += ent.pending.Tremor
                ent.pending.Tremor = 0
