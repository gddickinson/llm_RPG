"""NPC-vs-NPC conflict (P7.1) — the world fights its own battles.

Playtest 2 found cooperation/conflict invisible: hostile reputation only
moved prices, and ticker events resolved off screen. This system makes
the standing conflicts VISIBLE and mechanical, with zero LLM calls:

- Guards (and paladins) engage hostiles they can see, closing a tile a
  scan and swinging when adjacent — a patrol really fights a bandit
  near the road.
- Hostiles occasionally raid civilians the same way (slower cadence),
  so the brigand threat is real and guards have something to answer.
- Swings are logged with a `[Clash]` prefix only when the player is
  close enough to plausibly see them; defeats are always news.
- The player's own duel is sacred: hostiles adjacent to the player are
  left alone (no kill-stealing, no surprise rescues).

Cheap by construction: one distance scan every TICK_INTERVAL turns,
capped engagements per scan, no per-tick LLM use.
"""

import logging

logger = logging.getLogger("llm_rpg.npc_conflict")

SIGHT = 8              # tiles a guard notices an enemy across
RAID_SIGHT = 6         # hostiles hunting civilians look less far
TICK_INTERVAL = 3      # scan every N turns
RAID_MULTIPLE = 3      # raids happen every Nth scan
MAX_ENGAGEMENTS = 3    # fights progressed per scan
PLAYER_DUEL_RADIUS = 2  # hostiles this close to the player are theirs
CLASH_EARSHOT = 14     # log swings only this close to the player

GUARD_CLASSES = ("guard", "paladin")
HOSTILE_CLASSES = ("brigand", "monster", "troll")
CIVILIAN_CLASSES = ("villager", "merchant", "bard", "cleric")


def _cls(npc) -> str:
    return getattr(getattr(npc, "character_class", None), "value", "")


def _manhattan(a, b) -> int:
    return abs(a.position[0] - b.position[0]) + \
        abs(a.position[1] - b.position[1])


class NPCConflictSystem:
    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------ tick

    def update(self) -> int:
        """Progress visible conflicts. Returns engagements made."""
        engine = self.engine
        if engine.turn_counter % TICK_INTERVAL:
            return 0
        try:
            party = set(engine.companion_manager.party)
        except Exception:
            party = set()
        # Only combatants standing on the overworld map: zone NPCs
        # (tutorial island, interiors) have coordinates in a different
        # space and must never fight or be fought across grids.
        wmap = engine.world.map
        npcs = [n for n in engine.npc_manager.npcs.values()
                if n.is_active() and n.id not in party
                and wmap.get_character_at(*n.position) is n]
        guards = [n for n in npcs if _cls(n) in GUARD_CLASSES]
        hostiles = [n for n in npcs if _cls(n) in HOSTILE_CLASSES]
        civilians = [n for n in npcs if _cls(n) in CIVILIAN_CLASSES]
        if not hostiles:
            return 0

        player = engine.player
        fair_game = [h for h in hostiles
                     if _manhattan(h, player) > PLAYER_DUEL_RADIUS]
        engaged = 0
        for guard in guards:
            if engaged >= MAX_ENGAGEMENTS:
                break
            target = self._nearest(guard, fair_game, SIGHT)
            if target is not None:
                self._engage(guard, target)
                engaged += 1

        if engine.turn_counter % (TICK_INTERVAL * RAID_MULTIPLE) == 0:
            for hostile in fair_game:
                if engaged >= MAX_ENGAGEMENTS:
                    break
                target = self._nearest(hostile, civilians, RAID_SIGHT)
                if target is not None:
                    self._engage(hostile, target)
                    engaged += 1
        return engaged

    # --------------------------------------------------------- helpers

    def _nearest(self, npc, candidates, sight: int):
        best, best_d = None, sight + 1
        for other in candidates:
            if other.id == npc.id or not other.is_active():
                continue
            d = _manhattan(npc, other)
            if d < best_d:
                best, best_d = other, d
        return best

    def _engage(self, attacker, defender) -> None:
        combat = self.engine.combat_system
        try:
            ax, ay = attacker.position
            dx, dy = defender.position
            if ((ax - dx) ** 2 + (ay - dy) ** 2) ** 0.5 > 1.5:
                combat._step_toward(attacker, defender)
                return
            result = combat._resolve(attacker, defender)
            if _manhattan(attacker, self.engine.player) <= CLASH_EARSHOT:
                self.engine.memory_manager.add_event(f"[Clash] {result}")
        except Exception as e:
            logger.debug(f"engagement failed: {e}")
