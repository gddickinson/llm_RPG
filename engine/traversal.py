"""Environmental traversal (P11.1) — the land grades your passage.

Per-terrain rules live in `data/traversal.json`. Two shapes:

CROSSINGS (water, mountain) — terrain the map flatly blocked now
takes a graded check. Water at a shore (any dry neighbor) is
SHALLOW: anyone can wade, it just tires you. Deep water and rock
faces roll d20 + lattice skill level + ability modifier against a
DC raised by encumbrance (the P-carry pack) and exhaustion. Success
moves you, costs fatigue and minutes, and trains the skill
(Swimming for water, Agility for rock). Failure keeps you on your
side, tired; fail BADLY and the river or the rock takes a bite —
HP loss, floored at 1 (the story kills, not the current... until
P11.2 gives sweeps and drowning their own teeth).

SLOGS (swamp, dense forest) — passable ground that taxes you:
extra fatigue and minutes per step, telegraphed once on entry.

Fatigue is the NPC needs scale (0–100) on the player's metadata;
sleeping it off at an inn resets it. High skill means certainty:
at Agility 15 the climb check cannot fail — the old hard gates
became the mastery plateau.
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.traversal")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / \
    "traversal.json"
BAD_FAIL_MARGIN = 5      # miss the DC by this much and get hurt


def _load_rules() -> dict:
    try:
        with open(DATA_PATH) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"traversal.json unreadable: {e}")
        return {}


class TraversalSystem:
    def __init__(self, engine):
        self.engine = engine
        self.rules = _load_rules()
        self.rng = random.Random()

    # ------------------------------------------------------- queries

    def rule_for(self, terrain) -> Optional[dict]:
        return self.rules.get(getattr(terrain, "value", str(terrain)))

    def is_shallow(self, x: int, y: int) -> bool:
        """Water with any dry neighbor is wadeable shore."""
        wmap = self.engine.world.map
        if wmap.terrain[y][x] != TerrainType.WATER:
            return False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < wmap.width and 0 <= ny < wmap.height and \
                    wmap.terrain[ny][nx] != TerrainType.WATER:
                return True
        return False

    def aid_bonus(self, kind: str) -> int:
        """Gear and blessings help (P11.3): carried items with an
        equip_bonuses entry for the check kind ('climb'/'swim'),
        plus Swimmer's Grace for water."""
        player = self.engine.player
        bonus = 0
        carried = list(getattr(player, "inventory", []) or [])
        try:
            gear = getattr(player, "equipment", None)
            if gear is not None:
                carried += [it for it in vars(gear).values()
                            if it is not None]
        except Exception:
            pass
        for it in carried:
            bonuses = getattr(it, "equip_bonuses", None)
            if isinstance(bonuses, dict):
                bonus += int(bonuses.get(kind, 0))
        if kind == "swim":
            from characters.status_effects import has_effect
            if has_effect(player, "swimmers_grace"):
                bonus += 5
        return bonus

    def check_dc(self, rule: dict) -> int:
        """Base DC raised by pack weight and exhaustion."""
        from characters.needs import get_fatigue
        from engine.carry import capacity, used_slots
        player = self.engine.player
        dc = rule.get("base_dc", 12)
        load = used_slots(player) / max(1, capacity(player))
        if load >= 0.9:
            dc += 4
        elif load >= 0.6:
            dc += 2
        fatigue = get_fatigue(player)
        if fatigue >= 90:
            dc += 5
        elif fatigue >= 60:
            dc += 2
        return dc

    # ------------------------------------------------------ crossing

    def attempt_cross(self, nx: int, ny: int) -> Optional[str]:
        """Try to enter blocking terrain at (nx, ny). Returns a log
        message if a traversal rule applied (moved OR failed), else
        None. The caller learns success from the player position."""
        wmap = self.engine.world.map
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            return None
        rule = self.rule_for(wmap.terrain[ny][nx])
        if rule is None or rule.get("class") not in ("swim", "climb"):
            return None
        for npc in self.engine.npc_manager.npcs.values():
            if npc.is_active() and tuple(npc.position) == (nx, ny):
                return None
        player = self.engine.player
        # water walking: the surface bears you (P11.3)
        if rule.get("class") == "swim":
            from characters.status_effects import has_effect
            if has_effect(player, "water_walking"):
                self._move_to(nx, ny)
                msg = "You stride across the water's skin."
                self.engine.memory_manager.add_event(msg)
                return msg
        # shore water: anyone can wade
        if rule.get("wade_at_edge") and self.is_shallow(nx, ny):
            self._move_to(nx, ny)
            self._tire(rule.get("wade_fatigue", 5))
            self.engine.world.advance_time(
                rule.get("extra_minutes", 2))
            msg = f"You {rule.get('wade_verb', 'wade across')}."
            self.engine.memory_manager.add_event(msg)
            return msg
        # the graded check
        from engine.skill_progression import (add_skill_xp,
                                              get_skill_level)
        from engine.skills import ability_modifier
        skill = rule.get("skill", "agility")
        dc = self.check_dc(rule)
        d20 = self.rng.randint(1, 20)
        total = d20 + get_skill_level(player, skill) + \
            ability_modifier(getattr(player,
                                     rule.get("ability", "dexterity"),
                                     10)) + \
            self.aid_bonus(rule.get("class", ""))
        if total >= dc:
            self._move_to(nx, ny)
            self._tire(rule.get("fatigue", 10))
            self.engine.world.advance_time(
                rule.get("extra_minutes", 3))
            msg = f"You {rule.get('verb', 'cross')}. " \
                  f"(+{rule.get('xp', 5)} " \
                  f"{skill.capitalize()} XP)"
            self.engine.memory_manager.add_event(msg)
            for note in add_skill_xp(player, skill,
                                     rule.get("xp", 5)):
                self.engine.memory_manager.add_event(note)
            return msg
        self._tire(rule.get("fail_fatigue", 5))
        msg = rule.get("fail_line", "You can't find a way across.")
        self.engine.memory_manager.add_event(msg)
        if total <= dc - BAD_FAIL_MARGIN and rule.get("fail_hp"):
            player.take_damage(rule["fail_hp"])
            if player.hp <= 0:
                player.hp = 1        # scrapes maim; the story kills
            hurt = rule.get("hurt_line", "It hurts.")
            self.engine.memory_manager.add_event(
                f"{hurt} (-{rule['fail_hp']} HP)")
            if rule.get("class") == "climb":
                try:   # falling off the face you stood on (P11.2)
                    from engine.hazards import tumble
                    tumble(self.engine)
                except Exception:
                    pass
        return msg

    # --------------------------------------------------------- slogs

    def on_step(self, nx: int, ny: int) -> None:
        """Called after a normal successful step: slow ground and
        foul weather tax the walker."""
        self._weather_penalty(nx, ny)
        wmap = self.engine.world.map
        rule = self.rule_for(wmap.terrain[ny][nx])
        if rule is None or rule.get("class") != "slog":
            self.engine.player.metadata.pop("last_slog", None)
            return
        self._tire(rule.get("fatigue", 2))
        if rule.get("extra_minutes"):
            self.engine.world.advance_time(rule["extra_minutes"])
        line = rule.get("enter_line")
        if line and self.engine.player.metadata.get(
                "last_slog") != wmap.terrain[ny][nx].value:
            self.engine.memory_manager.add_event(line)
        self.engine.player.metadata["last_slog"] = \
            wmap.terrain[ny][nx].value

    def _weather_penalty(self, x: int, y: int) -> None:
        """Storms/snow slow travel off the roads: +1 min per step."""
        try:
            from world.weather import Weather
            current = self.engine.weather_system.state.current
            if current not in (Weather.STORM, Weather.SNOW):
                return
            if self.engine.world.map.terrain[y][x] == \
                    TerrainType.ROAD:
                return
            self.engine.world.advance_time(1)
            self._slow_steps = getattr(self, "_slow_steps", 0) + 1
            if self._slow_steps % 10 == 1:
                self.engine.memory_manager.add_event(
                    f"The {current.value} slows your travel.")
        except Exception:
            pass

    # ------------------------------------------------------- helpers

    def _move_to(self, nx: int, ny: int) -> None:
        player = self.engine.player
        wmap = self.engine.world.map
        old = player.position
        wmap.remove_character(player)
        player.position = (nx, ny)
        wmap.place_character(player, nx, ny)
        try:
            self.engine.pet_system.on_player_moved(old)
        except Exception:
            pass

    def _tire(self, amount: int) -> None:
        meta = self.engine.player.metadata
        meta["fatigue"] = min(100, meta.get("fatigue", 10) + amount)
