"""Companion / party system.

The player can recruit certain NPCs as companions. A companion:
- Follows the player around the map automatically.
- Fights enemies on the player's behalf.
- Shares loot and XP indirectly (combat XP goes to the player).

The party is stored as a list of NPC ids on the engine (`engine.party`).
"""

import logging
from typing import List, Optional

logger = logging.getLogger("llm_rpg.companions")

BANTER_EVERY = 45


def _load_banter():
    try:
        from items.data_loader import load_data_file
        return load_data_file("banter.json")
    except Exception:
        return {}


BANTER = _load_banter()


# Classes that can be recruited (heuristic mode)
RECRUITABLE_CLASSES = {"warrior", "bard", "cleric", "wizard", "ranger", "paladin"}


class CompanionManager:
    """Manage the player's party."""

    def __init__(self, engine):
        self.engine = engine
        self.party: List[str] = []   # NPC ids in the party

    # ---- recruit / dismiss ------------------------------------------

    def can_recruit(self, npc) -> str:
        """Return empty string if recruitable, otherwise a reason."""
        if npc.id in self.party:
            return "Already in your party."
        if not npc.is_active():
            return "They cannot join you now."
        klass = getattr(npc.character_class, "value", "")
        if klass not in RECRUITABLE_CLASSES:
            return f"A {klass} won't follow you."
        # Their faction must at least tolerate you (P12.11)
        try:
            from characters.factions import (Faction, threshold,
                                             faction_of_class)
            fac = faction_of_class(klass)
            if fac != Faction.NEUTRAL and threshold(
                    self.engine.player, fac) in ("disliked",
                                                 "despised"):
                return (f"{npc.name}'s people think too little of "
                        f"you to follow.")
        except Exception:
            pass
        # Need positive relationship
        if npc.get_relationship(self.engine.player.id) < 30:
            return f"{npc.name} doesn't trust you enough yet."
        cap = 3
        try:
            cap = self.engine.guild.companion_cap()
        except Exception:
            pass
        if len(self.party) >= cap:
            return f"Your party is full ({cap} max)."
        return ""

    def recruit(self, npc_id: str) -> str:
        npc = self.engine.npc_manager.get_npc(npc_id)
        if not npc:
            return "No such character."
        reason = self.can_recruit(npc)
        if reason:
            return reason
        self.party.append(npc_id)
        msg = f"{npc.name} joins your party!"
        self.engine.memory_manager.add_event(msg)
        npc.add_memory(f"I joined {self.engine.player.name}'s party.", 3)
        return msg

    def dismiss(self, npc_id: str) -> str:
        if npc_id not in self.party:
            return "They're not in your party."
        npc = self.engine.npc_manager.get_npc(npc_id)
        self.party.remove(npc_id)
        name = npc.name if npc else npc_id
        msg = f"{name} parts ways with you."
        self.engine.memory_manager.add_event(msg)
        return msg

    def members(self):
        return [self.engine.npc_manager.get_npc(nid) for nid in self.party
                if self.engine.npc_manager.get_npc(nid)]

    # ---- per-turn behavior ------------------------------------------

    def set_order(self, npc, order: str) -> str:
        """P15.5 tactical orders: follow (default) / hold / flee."""
        if order not in ("follow", "hold", "flee"):
            return "/order follow · hold · flee"
        npc.metadata["order"] = order
        lines = {"follow": f"{npc.name} falls in behind you.",
                 "hold": f"{npc.name} plants their feet: "
                         f"\"I hold here.\"",
                 "flee": f"{npc.name} nods: \"If it goes bad, "
                         f"I'm gone.\""}
        msg = lines[order]
        self.engine.memory_manager.add_event(msg)
        return msg

    def _flee_step(self, npc) -> bool:
        """Wounded and ordered to live: step away from the nearest
        hostile."""
        if npc.hp > npc.max_hp * 0.3:
            return False
        from engine.tactics import adjacent_hostiles
        foes = adjacent_hostiles(self.engine, npc.position)
        if not foes:
            return False
        fx, fy = foes[0].position
        cx, cy = npc.position
        dx = (cx > fx) - (cx < fx)
        dy = (cy > fy) - (cy < fy)
        moved = self.engine.world.map.move_character(
            npc, cx + dx, cy + dy)
        if moved:
            self.engine.memory_manager.add_event(
                f"{npc.name} breaks off, bleeding.")
        return bool(moved)

    def banter_tick(self) -> None:
        """P15.5: the road talks. One authored line every
        BANTER_EVERY quiet turns, cycling per companion."""
        members = [n for n in self.members() if n.is_active()]
        if not members:
            return
        meta = self.engine.player.metadata
        turn = self.engine.turn_counter
        if turn - meta.get("banter_turn", 0) < BANTER_EVERY:
            return
        meta["banter_turn"] = turn
        idx = meta.get("banter_idx", 0)
        speaker = members[idx % len(members)]
        lines = BANTER.get(speaker.id) or BANTER.get(
            "_class_" + getattr(speaker.character_class, "value",
                                ""), [])
        if not lines:
            return
        meta["banter_idx"] = idx + 1
        line = lines[(idx // max(1, len(members))) % len(lines)]
        self.engine.memory_manager.add_event(line)

    def update(self) -> None:
        """Move companions to follow the player and attack adjacent enemies."""
        from engine.squad_tactics import (player_focus_target, flank_tile,
                                          FOCUS_RADIUS)
        for npc in self.members():
            if not npc.is_active():
                continue
            order = npc.metadata.get("order", "follow")
            if order == "flee" and self._flee_step(npc):
                continue
            # Focus fire: the player's current target comes first (P7.3)
            focus = player_focus_target(self.engine)
            if focus is not None:
                fx, fy = focus.position
                cx, cy = npc.position
                d = ((cx - fx) ** 2 + (cy - fy) ** 2) ** 0.5
                if d <= 1.5:
                    # One free sidestep onto the flanking tile first —
                    # every later swing earns the +2
                    goal = flank_tile(self.engine, npc, focus)
                    if goal and goal != npc.position and \
                            max(abs(goal[0] - cx),
                                abs(goal[1] - cy)) <= 1 and \
                            self.engine.world.map.move_character(
                                npc, *goal):
                        continue
                    result = self.engine.combat_system._resolve(
                        npc, focus, "attack")
                    self.engine.memory_manager.add_event(result)
                    continue
                if d <= FOCUS_RADIUS:
                    goal = flank_tile(self.engine, npc, focus)
                    if goal and npc.position != goal:
                        from engine.squad_tactics import path_step
                        path_step(self.engine.world.map, npc, goal)
                        continue
            # Attack any adjacent enemy
            if self._companion_attack_nearby_enemy(npc):
                continue
            # Otherwise, follow — unless holding ground (P15.5)
            if order != "hold":
                self._companion_step_toward(
                    npc, self.engine.player.position)

    def _companion_attack_nearby_enemy(self, comp) -> bool:
        """If a hostile is adjacent, attack it. Return True if did."""
        cx, cy = comp.position
        for npc in self.engine.npc_manager.npcs.values():
            if npc.id == comp.id:
                continue
            if npc.id in self.party:
                continue
            if not npc.is_active():
                continue
            klass = getattr(npc.character_class, "value", "")
            if klass not in ("brigand", "monster", "troll"):
                continue
            nx, ny = npc.position
            d = ((cx - nx) ** 2 + (cy - ny) ** 2) ** 0.5
            if d <= 1.5:
                self.engine.combat_system.npc_attack(comp, npc.name, "attack")
                return True
        return False

    def _companion_step_toward(self, comp, target_pos) -> None:
        cx, cy = comp.position
        tx, ty = target_pos
        d = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
        if d <= 1.5:  # Already adjacent — stay put
            return
        # Real pathfinding: greedy steps trap in concave terrain (the
        # historic follow flake); BFS with a greedy fallback does not.
        from engine.squad_tactics import path_step
        path_step(self.engine.world.map, comp, (tx, ty))

    # ---- save / load ------------------------------------------------

    def to_dict(self):
        return {"party": list(self.party)}

    def from_dict(self, d):
        self.party = list(d.get("party", []))
