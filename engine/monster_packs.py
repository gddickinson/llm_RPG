"""Monster packs that fight as a group (P19.3).

Overworld monsters used to fight as a loose crowd: each picked the player
independently, and killing them was attritional. The Phase-17 battle AI
knows how to focus-fire, hold a leader and rout — but it is walled off in
the battle screen. This is the light bridge: each monster turn, before
the creatures act, we band the hostiles near the player into packs, name
a leader, and write two intents onto their metadata that the heuristic
brain already honours —

  * a shared **focus**: the whole pack piles onto ONE target, the softest
    thing it can reach (the player, or a weaker companion left exposed);
  * **morale by leader**: kill the leader and the survivors' nerve breaks
    — they turn and run.

A pack is either a lair's own occupants (P19.2 — they share a `lair`
tag) or a cluster of same-named beasts standing close together (a wolf
pack, a goblin band). Solo monsters and party-less fights are untouched:
a lone creature has no pack, and with no companions the focus is just the
player, exactly as before. Nothing persists — the tags are transient and
recomputed every turn. Heuristic, no per-tick LLM.
"""

import logging

logger = logging.getLogger("llm_rpg.monster_packs")

NEAR_PLAYER = 16         # only coordinate packs near the action
HOSTILE_CLASSES = ("monster", "troll", "brigand")
_TAGS = ("pack_id", "pack_leader_id", "focus_name", "pack_broken")


class MonsterPackSystem:
    def __init__(self, engine):
        self.engine = engine
        # pack_key -> leader id, remembered ACROSS turns so a leader's
        # death is recognised (a survivor-only regroup would just crown a
        # new leader and the pack would never break)
        self._leaders: dict = {}

    # ---- the per-turn pass -----------------------------------------

    def update(self) -> int:
        """Band nearby hostiles into packs and write their intents.
        Returns the number of packs coordinated."""
        near = [n for n in self.engine.npc_manager.npcs.values()
                if self._is_hostile(n) and self._near_player(n)]
        for m in near:                      # clear last turn's tags first
            for k in _TAGS:
                m.metadata.pop(k, None)
        groups: dict = {}
        for m in near:
            groups.setdefault(self._key(m), []).append(m)
        packs = 0
        for key, members in groups.items():
            if self._process(key, members):
                packs += 1
        return packs

    def _key(self, m) -> str:
        """A stable pack identity: a lair's own tag, else its kind."""
        lair = (m.metadata or {}).get("lair")
        return f"lair:{lair}" if lair else f"kind:{m.name}"

    # ---- membership ------------------------------------------------

    def _is_hostile(self, n) -> bool:
        if not n.is_active():
            return False
        if (getattr(n, "metadata", {}) or {}).get("player_char"):
            return False
        return getattr(n.character_class, "value", "") in HOSTILE_CLASSES

    def _near_player(self, n) -> bool:
        px, py = self.engine.player.position
        x, y = n.position
        return abs(x - px) + abs(y - py) <= NEAR_PLAYER

    # ---- coordination ----------------------------------------------

    def _process(self, key, members) -> bool:
        """Coordinate one candidate pack. Returns True if it IS a pack
        (a live band of 2+, or a band whose remembered leader just fell)."""
        npcs = self.engine.npc_manager.npcs
        leader_id = self._leaders.get(key)
        leader = npcs.get(leader_id) if leader_id else None
        leader_dead = leader_id is not None and (
            leader is None or not leader.is_active())

        if leader_dead:                       # the leader has fallen — rout
            for m in members:
                m.metadata["pack_broken"] = True
            return True
        if len(members) < 2:
            return False                      # a lone beast is not a pack
        if leader is None:                    # a new band crowns the strongest
            leader = max(members, key=lambda m: (m.max_hp, m.level))
            self._leaders[key] = leader.id

        focus = self._focus(members)
        fname = None if focus is None else (
            "player" if focus is self.engine.player else focus.name)
        for m in members:
            m.metadata["pack_id"] = leader.id
            m.metadata["pack_leader_id"] = leader.id
            if fname is not None:
                m.metadata["focus_name"] = fname
        return True

    def _focus(self, members):
        """The softest target the pack can reach — the player, or a weaker
        companion exposed nearby."""
        engine = self.engine
        cands = [engine.player]
        try:
            for cid in engine.companion_manager.party:
                c = engine.npc_manager.npcs.get(cid)
                if c is not None and c.is_active():
                    cands.append(c)
        except Exception:
            pass
        if len(cands) == 1:
            return engine.player
        cx = sum(m.position[0] for m in members) / len(members)
        cy = sum(m.position[1] for m in members) / len(members)
        near = [t for t in cands
                if abs(t.position[0] - cx) + abs(t.position[1] - cy)
                <= NEAR_PLAYER]
        if not near:
            return engine.player
        return min(near, key=lambda t: t.hp / max(1, t.max_hp))
