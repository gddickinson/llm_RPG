"""P37.6b — hostile aggression (George: monsters "just stand and get killed").

Every REAL turn, a hostile ADJACENT to the player PRESSES the attack — instead
of waiting for the ambient NPC AI, which acts only every `NPC_ACTION_INTERVAL`
(=5) turns, so an adjacent monster used to bite once per five of the player's
swings. Runs each turn from the pipeline, right after pursuit (which now closes
all the way to adjacent). ATTACK-ONLY (no movement — pursuit does the closing),
so a SHOVE that opens distance still buys a turn's respite. Reuses the pursuit
eligibility, so it skips party / fleeing / broken / zone-native creatures. A
struck hostile is tagged `_aggro_turn` so the throttled ambient AI doesn't also
swing that turn (no double attack).
"""


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class AggressionSystem:
    def __init__(self, engine):
        self.engine = engine

    def update(self) -> int:
        """Adjacent hostiles bite. Returns how many pressed the attack."""
        eng = self.engine
        player = getattr(eng, "player", None)
        if player is None or getattr(player, "hp", 1) <= 0:
            return 0
        # A player inside an interior / dungeon is in a SEPARATE coordinate
        # space — an overworld hostile sharing their interior-local coordinates
        # must NOT bite them (George 2026-07-15: an invisible Mire Stalker
        # attacked the hero in every building until dead).
        if getattr(eng, "current_interior", None) is not None or \
                getattr(eng, "current_dungeon", None) is not None:
            return 0
        ppos = tuple(player.position)
        wmap = eng.world.map
        try:
            party = set(eng.companion_manager.party)
        except Exception:
            party = set()
        pursuit = getattr(eng, "pursuit", None)
        cs = eng.combat_system
        acted = 0
        for npc in list(eng.npc_manager.npcs.values()):
            # melee reach only — a diagonal step counts as adjacent
            if _cheb(npc.position, ppos) > 1:
                continue
            if pursuit is not None and not pursuit._is_pursuer(npc, party, wmap):
                continue
            try:
                msg = cs._resolve(npc, player, "attack")
                if msg:
                    eng.memory_manager.add_event(msg)
                npc.metadata["_aggro_turn"] = eng.turn_counter
                acted += 1
            except Exception:
                pass
        return acted
