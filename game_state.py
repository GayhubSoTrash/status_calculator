from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import re
from typing import Any


DEBUFF_OPTIONS = ("震顫", "燒傷", "出血", "破裂", "腐蝕", "超高溫")


@dataclass
class Debuff:
    Tremor: int = 0
    Tremor_Burn: int = 0
    Burn: int = 0
    Bleed: int = 0
    Rupture: int = 0
    Corrosion: int = 0
    UTH: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "Tremor": self.Tremor,
            "Tremor_Burn": self.Tremor_Burn,
            "Burn": self.Burn,
            "Bleed": self.Bleed,
            "Rupture": self.Rupture,
            "Corrosion": self.Corrosion,
            "UTH": self.UTH,
        }


@dataclass
class Entity:
    id: int
    name: str
    # Internal cumulative values (used for history total formatting).
    damage: int = 0
    stager: int = 0

    # HP/MP (separate from damage/stager totals)
    hp_current: int = 0
    hp_max: int = 0
    mp_current: int = 0
    mp_max: int = 0

    # Damage-type resistances:
    # Each type has damage/stagger resistance.
    # These are numeric multipliers (e.g. 1.0 = normal, 2.0 = double).
    slash_damage_res: float = 1.0
    slash_stagger_res: float = 1.0
    piercing_damage_res: float = 1.0
    piercing_stagger_res: float = 1.0
    blunt_damage_res: float = 1.0
    blunt_stagger_res: float = 1.0

    # Stagger state lifecycle
    is_staggered: bool = False
    stagger_recover_turn: int | None = None

    debuff: Debuff = field(default_factory=Debuff)
    pending: Debuff = field(default_factory=Debuff)
    debuff_combo_choice: str = DEBUFF_OPTIONS[0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "damage": self.damage,
            "stager": self.stager,
            "hp_current": self.hp_current,
            "hp_max": self.hp_max,
            "mp_current": self.mp_current,
            "mp_max": self.mp_max,
            "resistances": {
                "slash_damage_res": self.slash_damage_res,
                "slash_stagger_res": self.slash_stagger_res,
                "piercing_damage_res": self.piercing_damage_res,
                "piercing_stagger_res": self.piercing_stagger_res,
                "blunt_damage_res": self.blunt_damage_res,
                "blunt_stagger_res": self.blunt_stagger_res,
            },
            "is_staggered": self.is_staggered,
            "stagger_recover_turn": self.stagger_recover_turn,
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

    def create_entity(
        self,
        name: str,
        hp_current: int,
        hp_max: int,
        mp_current: int,
        mp_max: int,
        slash_damage_res: float,
        slash_stagger_res: float,
        piercing_damage_res: float,
        piercing_stagger_res: float,
        blunt_damage_res: float,
        blunt_stagger_res: float,
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("目標名稱不能為空。")
        if hp_max <= 0 or mp_max <= 0:
            raise ValueError("HP/MP 最大值必須大於 0。")
        if hp_current < 0 or mp_current < 0:
            raise ValueError("HP/MP 當前值不能小於 0。")
        hp_current = min(hp_current, hp_max)
        mp_current = min(mp_current, mp_max)
        for v in [
            slash_damage_res,
            slash_stagger_res,
            piercing_damage_res,
            piercing_stagger_res,
            blunt_damage_res,
            blunt_stagger_res,
        ]:
            if v < 0:
                raise ValueError("抗性值不能小於 0。")
        ent = Entity(id=self._next_id, name=name)
        ent.hp_current = hp_current
        ent.hp_max = hp_max
        ent.mp_current = mp_current
        ent.mp_max = mp_max
        ent.slash_damage_res = float(slash_damage_res)
        ent.slash_stagger_res = float(slash_stagger_res)
        ent.piercing_damage_res = float(piercing_damage_res)
        ent.piercing_stagger_res = float(piercing_stagger_res)
        ent.blunt_damage_res = float(blunt_damage_res)
        ent.blunt_stagger_res = float(blunt_stagger_res)
        self._next_id += 1
        self.entities.append(ent)

    def delete_entity(self, entity_id: int) -> None:
        self.entities = [e for e in self.entities if e.id != entity_id]

    def clear_entity_damage_stager(self, entity_id: int) -> None:
        ent = self._get_entity(entity_id)
        ent.damage = 0
        ent.stager = 0

    def update_entity_stats(
        self,
        entity_id: int,
        hp_current: int,
        hp_max: int,
        mp_current: int,
        mp_max: int,
    ) -> None:
        ent = self._get_entity(entity_id)
        if hp_max <= 0 or mp_max <= 0:
            raise ValueError("HP/MP 最大值必須大於 0。")
        if hp_current < 0 or mp_current < 0:
            raise ValueError("HP/MP 當前值不能小於 0。")
        ent.hp_max = hp_max
        ent.mp_max = mp_max
        ent.hp_current = min(hp_current, hp_max)
        ent.mp_current = min(mp_current, mp_max)

    def update_entity_resistances(
        self,
        entity_id: int,
        slash_damage_res: float,
        slash_stagger_res: float,
        piercing_damage_res: float,
        piercing_stagger_res: float,
        blunt_damage_res: float,
        blunt_stagger_res: float,
    ) -> None:
        ent = self._get_entity(entity_id)
        for v in [
            slash_damage_res,
            slash_stagger_res,
            piercing_damage_res,
            piercing_stagger_res,
            blunt_damage_res,
            blunt_stagger_res,
        ]:
            if v < 0:
                raise ValueError("抗性值不能小於 0。")
        ent.slash_damage_res = float(slash_damage_res)
        ent.slash_stagger_res = float(slash_stagger_res)
        ent.piercing_damage_res = float(piercing_damage_res)
        ent.piercing_stagger_res = float(piercing_stagger_res)
        ent.blunt_damage_res = float(blunt_damage_res)
        ent.blunt_stagger_res = float(blunt_stagger_res)

    def attack_entity(
        self,
        entity_id: int,
        weapon_damage: str,
        damage_modifier: float,
        extra_damage: float,
        extra_stagger: float,
        damage_multiplier: float,
        stagger_multiplier: float,
        fixed_damage: float,
        fixed_stagger: float,
        damage_type: str,
        critical_hit: bool,
        dodge_fumble: bool,
        black_damage: bool,
    ) -> None:
        ent = self._get_entity(entity_id)
        pre_staggered = ent.is_staggered

        # Parse dice input and roll once (server-authoritative).
        weapon_kind, weapon_x, weapon_y, weapon_offset = self._parse_dice(weapon_damage)
        weapon_roll = self._roll_dice_sum(weapon_x, weapon_y) + weapon_offset
        weapon_min = weapon_x * 1 + weapon_offset
        weapon_max = weapon_x * weapon_y + weapon_offset

        # Damage-type mapping.
        damage_type_key = self._normalize_damage_type_key(damage_type)
        if damage_type_key == "slash":
            base_damage_res = ent.slash_damage_res
            base_stagger_res = ent.slash_stagger_res
        elif damage_type_key == "piercing":
            base_damage_res = ent.piercing_damage_res
            base_stagger_res = ent.piercing_stagger_res
        elif damage_type_key == "blunt":
            base_damage_res = ent.blunt_damage_res
            base_stagger_res = ent.blunt_stagger_res
        else:
            raise ValueError("未知傷害類型。")

        # Stagger-state override: treat resistances as 2.0 for attacks while already staggered.
        if pre_staggered:
            base_damage_res = 2.0
            base_stagger_res = 2.0

        if black_damage:
            mean_res = (base_damage_res + base_stagger_res) / 2.0
            base_damage_res = mean_res
            base_stagger_res = mean_res

        # Critical / dodge modify weapon damage and damage modifier.
        if critical_hit:
            weapon_used = weapon_max * 2
            dmg_mod_used = damage_modifier * 2
        elif dodge_fumble:
            weapon_used = weapon_roll * 2
            dmg_mod_used = damage_modifier * 2
        else:
            weapon_used = weapon_roll
            dmg_mod_used = damage_modifier

        damage_calc = (
            (weapon_used + dmg_mod_used + extra_damage)
            * damage_multiplier
            * base_damage_res
            + fixed_damage
        )
        stagger_calc = (
            (weapon_used + dmg_mod_used + extra_stagger)
            * stagger_multiplier
            * base_stagger_res
            + fixed_stagger
        )

        final_damage = max(0, int(math.floor(damage_calc + 1e-9)))
        final_stagger = max(0, int(math.floor(stagger_calc + 1e-9)))

        self._apply_damage_stagger_to_entity(
            ent,
            damage_delta=final_damage,
            stagger_delta=final_stagger,
            allow_stagger_entry=True,
        )

        # Attack log.
        damage_type_label = self._damage_type_label(damage_type_key)
        self._append_history(
            f"\"{ent.name}\" 受到 \"{final_damage}/{final_stagger}\" 點{damage_type_label}傷害"
        )

        # Attack-triggered debuffs (rupture + corrosion).
        self._rupture_activation(ent)
        self._corrosion_activation(ent)

        # Entry may already have happened via _apply_damage_stagger_to_entity.
        if (not pre_staggered) and ent.mp_current <= 0 and not ent.is_staggered:
            self._enter_stagger_state(ent)

    def _parse_dice(self, weapon_damage: str) -> tuple[str, int, int, int]:
        """
        Returns (kind, x, y, offset) where kind is 'dice' or 'int'.
        For an integer, x=1 and y=value? We normalize by treating it as Xd1.
        """
        s = str(weapon_damage).strip().lower()
        m = re.fullmatch(r"(\d+)\s*d\s*(\d+)\s*([+-]\s*\d+)?", s)
        if m:
            x = int(m.group(1))
            y = int(m.group(2))
            offset_text = m.group(3)
            offset = 0
            if offset_text:
                offset = int(offset_text.replace(" ", ""))
            if x <= 0 or y <= 0:
                raise ValueError("骰子格式無效。")
            return ("dice", x, y, offset)
        v = int(s)
        if v < 0:
            raise ValueError("武器傷害不能小於 0。")
        # Represent integer as Xd1 where min=max=v.
        # Use x=v and y=1 so min=v and max=v.
        return ("int", v, 1, 0)

    def _roll_dice_sum(self, x: int, y: int) -> int:
        if y == 1:
            return x
        return sum(random.randint(1, y) for _ in range(x))

    def _enter_stagger_state(self, ent: Entity) -> None:
        if ent.is_staggered:
            return
        ent.is_staggered = True
        ent.stagger_recover_turn = self.current_turn + 1
        self._append_history(f"\"{ent.name}\" 進入混亂狀態")

    def _apply_damage_stagger_to_entity(
        self,
        ent: Entity,
        damage_delta: int,
        stagger_delta: int,
        allow_stagger_entry: bool = True,
    ) -> None:
        d = max(0, int(damage_delta))
        s = max(0, int(stagger_delta))
        ent.hp_current = max(0, ent.hp_current - d)
        ent.mp_current = max(0, ent.mp_current - s)
        ent.damage += d
        ent.stager += s
        if allow_stagger_entry and (not ent.is_staggered) and ent.mp_current <= 0:
            self._enter_stagger_state(ent)

    def _normalize_damage_type_key(self, damage_type: str) -> str:
        d = str(damage_type).strip().lower()
        # Accept both keys and Chinese labels.
        mapping = {
            "slash": "slash",
            "斬擊": "slash",
            "piercing": "piercing",
            "突刺": "piercing",
            "blunt": "blunt",
            "打擊": "blunt",
            "blunt damage": "blunt",
        }
        if d not in mapping:
            # Also allow exact Chinese labels in Traditional.
            mapping_trad = {
                "斬擊": "slash",
                "突刺": "piercing",
                "打擊": "blunt",
            }
            if damage_type in mapping_trad:
                return mapping_trad[damage_type]
            raise ValueError("未知傷害類型。")
        return mapping[d]

    def _damage_type_label(self, damage_type_key: str) -> str:
        return {
            "slash": "斬擊",
            "piercing": "突刺",
            "blunt": "打擊",
        }.get(damage_type_key, damage_type_key)

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
        elif debuff_key == "UTH":
            self._uth_activation(ent)
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
        # Damage/stagger totals are per-turn log formatting only.
        # Clear them when settlement starts so totals reflect only this turn.
        for ent in self.entities:
            ent.damage = 0
            ent.stager = 0
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
        if debuff_key not in {"Tremor_Burn", "Burn", "Bleed", "Rupture", "Corrosion", "UTH"}:
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
        elif choice == "超高溫":
            ent.debuff.UTH += 1

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
        elif choice == "超高溫":
            ent.pending.UTH += 1

    def _burn_activation(self, ent: Entity, consume: bool = True) -> None:
        if ent.debuff.Burn > 0:
            before_stack = ent.debuff.Burn
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=ent.debuff.Burn, stagger_delta=0, allow_stagger_entry=True
            )
            if consume:
                ent.debuff.Burn = ent.debuff.Burn * 2 // 3
            self._record_activation(
                ent, "燒傷", damage_delta=before_stack, stack_after=ent.debuff.Burn
            )

    def _bleed_activation(self, ent: Entity) -> None:
        if ent.debuff.Bleed > 0:
            before_stack = ent.debuff.Bleed
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=ent.debuff.Bleed, stagger_delta=0, allow_stagger_entry=True
            )
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
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=ent.debuff.Rupture, stagger_delta=0, allow_stagger_entry=True
            )
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
            self._apply_damage_stagger_to_entity(
                ent,
                damage_delta=ent.debuff.Corrosion,
                stagger_delta=ent.debuff.Corrosion,
                allow_stagger_entry=True,
            )
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

    def _uth_activation(self, ent: Entity) -> None:
        """
        UTH activation happens once per settlement:
        - Deal stagger equal to current Burn stack
        - Consume 1 UTH stack
        Triggered before Burn at turn end.
        """
        if ent.debuff.UTH > 0:
            before_stack = ent.debuff.UTH
            burn_stack = ent.debuff.Burn
            stager_delta = burn_stack
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=0, stagger_delta=stager_delta, allow_stagger_entry=True
            )
            ent.debuff.UTH = max(0, ent.debuff.UTH - 1)
            # Log with merged damage/stagger format (damage_delta=0).
            self._record_activation(
                ent,
                "超高溫",
                damage_delta=0,
                stager_delta=stager_delta,
                stack_after=ent.debuff.UTH,
            )

    def _tremor_burst(self, ent: Entity, consume: bool) -> None:
        if ent.debuff.Tremor_Burn > 0:
            before_stack = ent.debuff.Tremor_Burn
            self._apply_damage_stagger_to_entity(
                ent,
                damage_delta=ent.debuff.Tremor_Burn,
                stagger_delta=ent.debuff.Tremor_Burn,
                allow_stagger_entry=True,
            )
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
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=0, stagger_delta=ent.debuff.Tremor, allow_stagger_entry=True
            )
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
        if p.UTH > 0:
            d.UTH += p.UTH
            self._record_next_turn_gain(ent, "超高溫", p.UTH, d.UTH)
        ent.pending = Debuff()

    def _apply_turn_end_for_entity(self, ent: Entity) -> None:
        # UTH triggers before Burn at settlement.
        self._uth_activation(ent)
        self._burn_activation(ent, True)
        self._tremor_burst(ent, True)
        self._bleed_decay(ent)
        self._rupture_decay(ent)
        self._corrosion_decay(ent)

        # Stagger state recovery happens at end of the target settlement.
        if ent.is_staggered and ent.stagger_recover_turn == self.current_turn:
            ent.is_staggered = False
            ent.stagger_recover_turn = None
            ent.mp_current = ent.mp_max
            self._append_history(f"\"{ent.name}\"從混亂狀態恢復")

    def _normalize_tremor_pairs(self) -> None:
        for ent in self.entities:
            if ent.debuff.Tremor > 0 and ent.debuff.Tremor_Burn > 0:
                ent.debuff.Tremor_Burn += ent.debuff.Tremor
                ent.debuff.Tremor = 0
            if ent.pending.Tremor > 0 and ent.pending.Tremor_Burn > 0:
                ent.pending.Tremor_Burn += ent.pending.Tremor
                ent.pending.Tremor = 0
