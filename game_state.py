from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import re
from typing import Any


DEBUFF_OPTIONS = ("震顫", "燒傷", "出血", "破裂", "腐蝕", "超高溫", "保護", "振奮", "易損", "麻痺")
MAX_UNDO_STEPS = 3
RESISTANCE_LEVELS = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0)


@dataclass
class Debuff:
    Tremor: int = 0
    Tremor_Burn: int = 0
    Burn: int = 0
    Bleed: int = 0
    Rupture: int = 0
    Corrosion: int = 0
    UTH: int = 0
    Protection: int = 0
    StaggerProtection: int = 0
    Vulnerable: int = 0
    Paralyze: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "Tremor": self.Tremor,
            "Tremor_Burn": self.Tremor_Burn,
            "Burn": self.Burn,
            "Bleed": self.Bleed,
            "Rupture": self.Rupture,
            "Corrosion": self.Corrosion,
            "UTH": self.UTH,
            "Protection": self.Protection,
            "StaggerProtection": self.StaggerProtection,
            "Vulnerable": self.Vulnerable,
            "Paralyze": self.Paralyze,
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

    # Speed: spec "XdY+Z/A" (omit /A for A=1); A independent rolls of the dice expression.
    speed_spec: str = "1d6"
    speed_values: list[int] = field(default_factory=list)

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
            "speed_spec": self.speed_spec,
            "speed_values": list(self.speed_values),
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
        self.undo_stack: list[tuple[str, dict[str, Any]]] = []
        self.redo_stack: list[tuple[str, dict[str, Any]]] = []

    def snapshot(self) -> dict[str, Any]:
        self._normalize_tremor_pairs()
        return {
            "turn": self.current_turn,
            "entities": [e.as_dict() for e in self.entities],
            "history_logs": list(self.history_logs),
            "debuff_options": DEBUFF_OPTIONS,
            "undo_count": len(self.undo_stack),
            "redo_count": len(self.redo_stack),
        }

    def create_entity(
        self,
        name: str,
        speed_spec: str,
        hp_max: int,
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
        self._parse_speed_spec(str(speed_spec).strip())
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
        ent.speed_spec = str(speed_spec).strip()
        ent.hp_current = hp_max
        ent.hp_max = hp_max
        ent.mp_current = mp_max
        ent.mp_max = mp_max
        ent.slash_damage_res = float(slash_damage_res)
        ent.slash_stagger_res = float(slash_stagger_res)
        ent.piercing_damage_res = float(piercing_damage_res)
        ent.piercing_stagger_res = float(piercing_stagger_res)
        ent.blunt_damage_res = float(blunt_damage_res)
        ent.blunt_stagger_res = float(blunt_stagger_res)
        self._next_id += 1
        self.entities.append(ent)
        self._roll_all_speeds(ent)

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
        damage_resistance_downgrade: int,
        stagger_resistance_downgrade: int,
        critical_hit: bool,
        dodge_fumble: bool,
        black_damage: bool,
    ) -> None:
        ent = self._get_entity(entity_id)
        pre_staggered = ent.is_staggered

        # Parse dice input and roll once (server-authoritative).
        _weapon_kind, weapon_x, weapon_y, weapon_offset = self._parse_dice(weapon_damage)
        weapon_roll = self._roll_dice_sum(weapon_x, weapon_y) + weapon_offset
        weapon_min = weapon_x * 1 + weapon_offset
        weapon_max = weapon_x * weapon_y + weapon_offset

        damage_type_key = self._normalize_damage_type_key(damage_type)
        base_damage_res, base_stagger_res = self._resolve_attack_resistances(
            ent,
            damage_type_key,
            pre_staggered,
            black_damage,
            damage_resistance_downgrade,
            stagger_resistance_downgrade,
        )

        # Critical / dodge behavior on weapon roll only:
        # - critical: use max roll and *2
        # - dodge_fumble: *2 on weapon roll
        # - both: max roll *4
        if critical_hit and dodge_fumble:
            weapon_used = weapon_max * 4
        elif critical_hit:
            weapon_used = weapon_max * 2
        elif dodge_fumble:
            weapon_used = weapon_roll * 2
        else:
            weapon_used = weapon_roll
        dmg_mod_used = damage_modifier
        attack_extra_damage = extra_damage + ent.debuff.Vulnerable - ent.debuff.Protection
        attack_extra_stagger = extra_stagger - ent.debuff.StaggerProtection

        damage_calc = (
            (weapon_used + dmg_mod_used + attack_extra_damage)
            * damage_multiplier
            * base_damage_res
            + fixed_damage
        )
        stagger_calc = (
            (weapon_used + dmg_mod_used + attack_extra_stagger)
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
            # For attack flow, log attack first, then enter-stagger log.
            allow_stagger_entry=False,
        )

        # Attack log (includes per-turn total like debuffs).
        damage_type_label = self._damage_type_label(damage_type_key)
        self._append_history(
            f"\"{ent.name}\" 受到 \"{final_damage}/{final_stagger}\" 點{damage_type_label}傷害，"
            f"總計傷害為\"{ent.damage}/{ent.stager}\""
        )

        # Attack-triggered debuffs (rupture + corrosion).
        self._rupture_activation(ent)
        self._corrosion_activation(ent)

        # Attack-triggered stagger-state log must appear after attack log.
        if (not pre_staggered) and ent.mp_current <= 0 and not ent.is_staggered:
            self._enter_stagger_state(ent)

    def calculate_attack_preview(
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
        damage_resistance_downgrade: int,
        stagger_resistance_downgrade: int,
        critical_hit: bool,
        dodge_fumble: bool,
        black_damage: bool,
    ) -> dict[str, int]:
        ent = self._get_entity(entity_id)
        _weapon_kind, weapon_x, weapon_y, weapon_offset = self._parse_dice(weapon_damage)
        weapon_min = weapon_x * 1 + weapon_offset
        weapon_max = weapon_x * weapon_y + weapon_offset
        damage_type_key = self._normalize_damage_type_key(damage_type)

        base_damage_res, base_stagger_res = self._resolve_attack_resistances(
            ent,
            damage_type_key,
            ent.is_staggered,
            black_damage,
            damage_resistance_downgrade,
            stagger_resistance_downgrade,
        )

        if critical_hit and dodge_fumble:
            weapon_min_used = weapon_max * 4
            weapon_max_used = weapon_max * 4
        elif critical_hit:
            weapon_min_used = weapon_max * 2
            weapon_max_used = weapon_max * 2
        elif dodge_fumble:
            weapon_min_used = weapon_min * 2
            weapon_max_used = weapon_max * 2
        else:
            weapon_min_used = weapon_min
            weapon_max_used = weapon_max

        dmg_mod_used = damage_modifier
        attack_extra_damage = extra_damage + ent.debuff.Vulnerable - ent.debuff.Protection
        attack_extra_stagger = extra_stagger - ent.debuff.StaggerProtection

        min_damage = max(
            0,
            int(
                math.floor(
                    (
                        (weapon_min_used + dmg_mod_used + attack_extra_damage)
                        * damage_multiplier
                        * base_damage_res
                        + fixed_damage
                    )
                    + 1e-9
                )
            ),
        )
        max_damage = max(
            0,
            int(
                math.floor(
                    (
                        (weapon_max_used + dmg_mod_used + attack_extra_damage)
                        * damage_multiplier
                        * base_damage_res
                        + fixed_damage
                    )
                    + 1e-9
                )
            ),
        )
        min_stagger = max(
            0,
            int(
                math.floor(
                    (
                        (weapon_min_used + dmg_mod_used + attack_extra_stagger)
                        * stagger_multiplier
                        * base_stagger_res
                        + fixed_stagger
                    )
                    + 1e-9
                )
            ),
        )
        max_stagger = max(
            0,
            int(
                math.floor(
                    (
                        (weapon_max_used + dmg_mod_used + attack_extra_stagger)
                        * stagger_multiplier
                        * base_stagger_res
                        + fixed_stagger
                    )
                    + 1e-9
                )
            ),
        )
        return {
            "min_damage": min_damage,
            "max_damage": max_damage,
            "min_stagger": min_stagger,
            "max_stagger": max_stagger,
        }

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

    def _parse_speed_spec(self, s: str) -> tuple[str, int]:
        """
        Parse 'XdY+Z/A' or 'XdY+Z'. Returns (dice_segment_for_roll, A).
        A defaults to 1 if '/A' is omitted.
        """
        text = str(s).strip()
        if not text:
            raise ValueError("速度規格不能為空。")
        if "/" in text:
            dice_part, a_part = text.rsplit("/", 1)
            dice_part = dice_part.strip()
            a_part = a_part.strip()
            if not dice_part:
                raise ValueError("速度規格格式錯誤。")
            try:
                a = int(a_part)
            except ValueError as exc:
                raise ValueError("速度數量 A 必須為正整數。") from exc
            if a <= 0:
                raise ValueError("速度數量 A 必須為正整數。")
        else:
            dice_part = text
            a = 1
        self._parse_dice(dice_part)
        return (dice_part, a)

    def _single_speed_roll(self, dice_part: str) -> int:
        kind, x, y, offset = self._parse_dice(dice_part.strip())
        r = self._roll_dice_sum(x, y)
        if kind == "dice":
            return r + offset
        return r

    def _roll_all_speeds(self, ent: Entity) -> None:
        dice_part, count = self._parse_speed_spec(ent.speed_spec)
        ent.speed_values = [self._single_speed_roll(dice_part) for _ in range(count)]
        parts = "、".join(str(v) for v in ent.speed_values)
        self._append_history(f"\"{ent.name}\" 的速度為 {parts}")

    def _next_duplicate_name(self, source_name: str) -> str:
        base = source_name.strip()
        used = {e.name for e in self.entities}
        candidate = f"{base} (複製)"
        if candidate not in used:
            return candidate
        n = 2
        while True:
            c = f"{base} (複製{n})"
            if c not in used:
                return c
            n += 1

    def update_entity_speed(self, entity_id: int, speed_spec: str, speed_values: list[Any]) -> None:
        ent = self._get_entity(entity_id)
        spec = str(speed_spec).strip()
        _, a = self._parse_speed_spec(spec)
        try:
            vals = [int(x) for x in speed_values]
        except (TypeError, ValueError) as exc:
            raise ValueError("速度數值必須為整數。") from exc
        if len(vals) != a:
            raise ValueError("速度數值數量必須與速度規格中的數量一致。")
        for v in vals:
            if v < 0:
                raise ValueError("速度值不能小於 0。")
        ent.speed_spec = spec
        ent.speed_values = vals

    def duplicate_entity(self, entity_id: int) -> None:
        src = self._get_entity(entity_id)
        new_name = self._next_duplicate_name(src.name)
        ent = Entity(
            id=self._next_id,
            name=new_name,
            damage=src.damage,
            stager=src.stager,
            hp_current=src.hp_current,
            hp_max=src.hp_max,
            mp_current=src.mp_current,
            mp_max=src.mp_max,
            slash_damage_res=src.slash_damage_res,
            slash_stagger_res=src.slash_stagger_res,
            piercing_damage_res=src.piercing_damage_res,
            piercing_stagger_res=src.piercing_stagger_res,
            blunt_damage_res=src.blunt_damage_res,
            blunt_stagger_res=src.blunt_stagger_res,
            is_staggered=src.is_staggered,
            stagger_recover_turn=src.stagger_recover_turn,
            debuff=Debuff(**src.debuff.as_dict()),
            pending=Debuff(**src.pending.as_dict()),
            debuff_combo_choice=src.debuff_combo_choice,
            speed_spec=src.speed_spec,
            speed_values=list(src.speed_values),
        )
        self._next_id += 1
        self.entities.append(ent)

    def _resolve_attack_resistances(
        self,
        ent: Entity,
        damage_type_key: str,
        pre_staggered: bool,
        black_damage: bool,
        damage_resistance_downgrade: int = 0,
        stagger_resistance_downgrade: int = 0,
    ) -> tuple[float, float]:
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

        if pre_staggered:
            base_damage_res = 2.0
            base_stagger_res = 2.0

        if black_damage:
            mean_res = (base_damage_res + base_stagger_res) / 2.0
            base_damage_res = mean_res
            base_stagger_res = mean_res

        base_damage_res = self._apply_resistance_downgrade_levels(
            base_damage_res, damage_resistance_downgrade
        )
        base_stagger_res = self._apply_resistance_downgrade_levels(
            base_stagger_res, stagger_resistance_downgrade
        )

        return base_damage_res, base_stagger_res

    def _apply_resistance_downgrade_levels(self, value: float, downgrade_levels: int) -> float:
        n = max(0, int(downgrade_levels))
        if n <= 0:
            return float(value)
        start_idx = 0
        for i, lvl in enumerate(RESISTANCE_LEVELS):
            if value <= lvl:
                start_idx = i
                break
        else:
            start_idx = len(RESISTANCE_LEVELS) - 1
        end_idx = min(start_idx + n, len(RESISTANCE_LEVELS) - 1)
        return float(RESISTANCE_LEVELS[end_idx])

    def _enter_stagger_state(self, ent: Entity) -> None:
        if ent.is_staggered:
            return
        ent.is_staggered = True
        ent.stagger_recover_turn = self.current_turn + 1
        self._append_history(f"\"{ent.name}\" 進入混亂狀態")

    def _enter_stagger_state_if_needed(self, ent: Entity) -> None:
        if (not ent.is_staggered) and ent.mp_current <= 0:
            self._enter_stagger_state(ent)

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

    def record_undo_checkpoint(self, operation_type: str) -> None:
        self.undo_stack.append((operation_type, self._export_state()))
        if len(self.undo_stack) > MAX_UNDO_STEPS:
            self.undo_stack = self.undo_stack[-MAX_UNDO_STEPS:]
        self.redo_stack.clear()

    def undo_last(self) -> None:
        if not self.undo_stack:
            raise ValueError("沒有可撤回的操作。")
        operation_type, snapshot_before = self.undo_stack.pop()
        self.redo_stack.append((operation_type, self._export_state()))
        if len(self.redo_stack) > MAX_UNDO_STEPS:
            self.redo_stack = self.redo_stack[-MAX_UNDO_STEPS:]
        self._import_state(snapshot_before)
        self._append_history(f"撤回了一次“{operation_type}”")

    def redo_last(self) -> None:
        if not self.redo_stack:
            raise ValueError("沒有可重做的操作。")
        operation_type, snapshot_after = self.redo_stack.pop()
        self.undo_stack.append((operation_type, self._export_state()))
        if len(self.undo_stack) > MAX_UNDO_STEPS:
            self.undo_stack = self.undo_stack[-MAX_UNDO_STEPS:]
        self._import_state(snapshot_after)
        self._append_history(f"重做了一次“{operation_type}”")

    def set_combo_choice(self, entity_id: int, choice: str) -> None:
        ent = self._get_entity(entity_id)
        ent.debuff_combo_choice = self._normalize_choice(choice)

    def grant_now(self, entity_id: int, choice: str | None = None) -> None:
        ent = self._get_entity(entity_id)
        selected = self._normalize_choice(choice or ent.debuff_combo_choice)
        ent.debuff_combo_choice = selected
        self._grant_stack_by_choice(ent.debuff, ent, selected, for_pending=False)
        self._normalize_tremor_pairs()

    def grant_next(self, entity_id: int, choice: str | None = None) -> None:
        ent = self._get_entity(entity_id)
        selected = self._normalize_choice(choice or ent.debuff_combo_choice)
        ent.debuff_combo_choice = selected
        self._grant_stack_by_choice(ent.pending, ent, selected, for_pending=True)
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
        elif debuff_key in {"Protection", "StaggerProtection", "Vulnerable", "Paralyze"}:
            raise ValueError("此效果不能手動觸發。")
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
            self._clear_turn_end_temporary_stacks(ent)
        self._append_history(f"-------第{self.current_turn + 1}幕開始-------")
        for ent in self.entities:
            self._roll_all_speeds(ent)
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
        if debuff_key not in {
            "Tremor_Burn",
            "Burn",
            "Bleed",
            "Rupture",
            "Corrosion",
            "UTH",
            "Protection",
            "StaggerProtection",
            "Vulnerable",
            "Paralyze",
        }:
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

    def _grant_stack_by_choice(self, target: Debuff, ent: Entity, choice: str, for_pending: bool) -> None:
        if choice == "震顫":
            if for_pending:
                self._inc_tremor_on_pending(ent)
            else:
                self._inc_tremor_on_debuff(ent)
        elif choice == "燒傷":
            target.Burn += 1
        elif choice == "出血":
            target.Bleed += 1
        elif choice == "破裂":
            target.Rupture += 1
        elif choice == "腐蝕":
            target.Corrosion += 1
        elif choice == "超高溫":
            target.UTH += 1
        elif choice == "保護":
            target.Protection += 1
        elif choice == "振奮":
            target.StaggerProtection += 1
        elif choice == "易損":
            target.Vulnerable += 1
        elif choice == "麻痺":
            target.Paralyze += 1

    def _burn_activation(self, ent: Entity, consume: bool = True) -> None:
        if ent.debuff.Burn > 0:
            before_stack = ent.debuff.Burn
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=ent.debuff.Burn, stagger_delta=0, allow_stagger_entry=False
            )
            if consume:
                ent.debuff.Burn = ent.debuff.Burn * 2 // 3
            self._record_activation(
                ent, "燒傷", damage_delta=before_stack, stack_after=ent.debuff.Burn
            )
            self._enter_stagger_state_if_needed(ent)

    def _bleed_activation(self, ent: Entity) -> None:
        if ent.debuff.Bleed > 0:
            before_stack = ent.debuff.Bleed
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=ent.debuff.Bleed, stagger_delta=0, allow_stagger_entry=False
            )
            ent.debuff.Bleed = math.ceil(ent.debuff.Bleed * 2 / 3)
            self._record_activation(
                ent, "出血", damage_delta=before_stack, stack_after=ent.debuff.Bleed
            )
            self._enter_stagger_state_if_needed(ent)

    def _bleed_decay(self, ent: Entity) -> None:
        if ent.debuff.Bleed > 0:
            ent.debuff.Bleed = math.ceil(ent.debuff.Bleed * 2 / 3)
            self._record_settlement_decay(ent, "出血", ent.debuff.Bleed)

    def _rupture_activation(self, ent: Entity) -> None:
        if ent.debuff.Rupture > 0:
            before_stack = ent.debuff.Rupture
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=ent.debuff.Rupture, stagger_delta=0, allow_stagger_entry=False
            )
            ent.debuff.Rupture = math.ceil(ent.debuff.Rupture * 2 / 3)
            self._record_activation(
                ent, "破裂", damage_delta=before_stack, stack_after=ent.debuff.Rupture
            )
            self._enter_stagger_state_if_needed(ent)

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
                allow_stagger_entry=False,
            )
            self._record_activation(
                ent,
                "腐蝕",
                damage_delta=before_stack,
                stager_delta=before_stack,
                stack_after=ent.debuff.Corrosion,
            )
            self._enter_stagger_state_if_needed(ent)

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
                ent, damage_delta=0, stagger_delta=stager_delta, allow_stagger_entry=False
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
            self._enter_stagger_state_if_needed(ent)

    def _tremor_burst(self, ent: Entity, consume: bool) -> None:
        if ent.debuff.Tremor_Burn > 0:
            before_stack = ent.debuff.Tremor_Burn
            self._apply_damage_stagger_to_entity(
                ent,
                damage_delta=ent.debuff.Tremor_Burn,
                stagger_delta=ent.debuff.Tremor_Burn,
                allow_stagger_entry=False,
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
            self._enter_stagger_state_if_needed(ent)
        elif ent.debuff.Tremor > 0:
            before_stack = ent.debuff.Tremor
            self._apply_damage_stagger_to_entity(
                ent, damage_delta=0, stagger_delta=ent.debuff.Tremor, allow_stagger_entry=False
            )
            if consume:
                ent.debuff.Tremor = ent.debuff.Tremor * 2 // 3
            self._record_activation(
                ent, "震顫", stager_delta=before_stack, stack_after=ent.debuff.Tremor
            )
            self._enter_stagger_state_if_needed(ent)

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
        if p.Protection > 0:
            d.Protection += p.Protection
            self._record_next_turn_gain(ent, "保護", p.Protection, d.Protection)
        if p.StaggerProtection > 0:
            d.StaggerProtection += p.StaggerProtection
            self._record_next_turn_gain(ent, "振奮", p.StaggerProtection, d.StaggerProtection)
        if p.Vulnerable > 0:
            d.Vulnerable += p.Vulnerable
            self._record_next_turn_gain(ent, "易損", p.Vulnerable, d.Vulnerable)
        if p.Paralyze > 0:
            d.Paralyze += p.Paralyze
            self._record_next_turn_gain(ent, "麻痺", p.Paralyze, d.Paralyze)
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

    def _clear_turn_end_temporary_stacks(self, ent: Entity) -> None:
        ent.debuff.Protection = 0
        ent.debuff.StaggerProtection = 0
        ent.debuff.Vulnerable = 0
        ent.debuff.Paralyze = 0

    def _export_state(self) -> dict[str, Any]:
        return {
            "current_turn": self.current_turn,
            "next_id": self._next_id,
            "entities": [e.as_dict() for e in self.entities],
            "history_logs": list(self.history_logs),
        }

    def _import_state(self, data: dict[str, Any]) -> None:
        self.current_turn = int(data.get("current_turn", 1))
        self._next_id = int(data.get("next_id", 1))
        self.history_logs = list(data.get("history_logs", []))
        self.entities = [self._entity_from_dict(raw) for raw in data.get("entities", [])]

    def _debuff_from_dict(self, raw: dict[str, Any]) -> Debuff:
        return Debuff(
            Tremor=int(raw.get("Tremor", 0)),
            Tremor_Burn=int(raw.get("Tremor_Burn", 0)),
            Burn=int(raw.get("Burn", 0)),
            Bleed=int(raw.get("Bleed", 0)),
            Rupture=int(raw.get("Rupture", 0)),
            Corrosion=int(raw.get("Corrosion", 0)),
            UTH=int(raw.get("UTH", 0)),
            Protection=int(raw.get("Protection", 0)),
            StaggerProtection=int(raw.get("StaggerProtection", 0)),
            Vulnerable=int(raw.get("Vulnerable", 0)),
            Paralyze=int(raw.get("Paralyze", 0)),
        )

    def _entity_from_dict(self, raw: dict[str, Any]) -> Entity:
        res = raw.get("resistances", {})
        sv_raw = raw.get("speed_values")
        if sv_raw is not None:
            speed_values = [int(x) for x in list(sv_raw)]
        else:
            legacy = raw.get("speed_value")
            speed_values = [int(legacy)] if legacy is not None else []
        ent = Entity(
            id=int(raw.get("id", 0)),
            name=str(raw.get("name", "")),
            damage=int(raw.get("damage", 0)),
            stager=int(raw.get("stager", 0)),
            hp_current=int(raw.get("hp_current", 0)),
            hp_max=int(raw.get("hp_max", 0)),
            mp_current=int(raw.get("mp_current", 0)),
            mp_max=int(raw.get("mp_max", 0)),
            slash_damage_res=float(res.get("slash_damage_res", 1.0)),
            slash_stagger_res=float(res.get("slash_stagger_res", 1.0)),
            piercing_damage_res=float(res.get("piercing_damage_res", 1.0)),
            piercing_stagger_res=float(res.get("piercing_stagger_res", 1.0)),
            blunt_damage_res=float(res.get("blunt_damage_res", 1.0)),
            blunt_stagger_res=float(res.get("blunt_stagger_res", 1.0)),
            is_staggered=bool(raw.get("is_staggered", False)),
            stagger_recover_turn=raw.get("stagger_recover_turn"),
            debuff=self._debuff_from_dict(raw.get("debuff", {})),
            pending=self._debuff_from_dict(raw.get("pending", {})),
            debuff_combo_choice=self._normalize_choice(str(raw.get("debuff_combo_choice", DEBUFF_OPTIONS[0]))),
            speed_spec=str(raw.get("speed_spec", "1d6")),
            speed_values=speed_values,
        )
        if ent.stagger_recover_turn is not None:
            ent.stagger_recover_turn = int(ent.stagger_recover_turn)
        return ent

    def _normalize_tremor_pairs(self) -> None:
        for ent in self.entities:
            if ent.debuff.Tremor > 0 and ent.debuff.Tremor_Burn > 0:
                ent.debuff.Tremor_Burn += ent.debuff.Tremor
                ent.debuff.Tremor = 0
            if ent.pending.Tremor > 0 and ent.pending.Tremor_Burn > 0:
                ent.pending.Tremor_Burn += ent.pending.Tremor
                ent.pending.Tremor = 0
