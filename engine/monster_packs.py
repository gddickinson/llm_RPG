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
_TAGS = ("pack_id", "pack_leader_id", "focus_name", "pack_broken",
         "focus_pos", "approach_pos", "pack_role")
# P35.1 soft, high-value targets the pack prioritises — a caster/archer hurts most
_SQUISHY = ("wizard", "sorcerer", "warlock", "cleric", "druid", "ranger",
            "bard", "archer", "mage")
FINISH_HP = 7            # a target this low is worth ganging up to FINISH
WOUNDED_FRAC = 0.28      # below this a pack member breaks off to save itself


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
        # P35.2 a pack that is clearly LOSING withdraws together to regroup rather
        # than feeding itself in piecemeal — a real defensive call
        outmatched = self._outmatched(members)
        # P35.1 assign each member a ROLE and a distinct SURROUND tile, so the
        # pack fans out to flank the focus (earning the +2 flank), ranged types
        # keep their distance, and the wounded peel off — instead of all stacking
        taken = set()
        for m in members:
            m.metadata["pack_id"] = leader.id
            m.metadata["pack_leader_id"] = leader.id
            if fname is None:
                continue
            m.metadata["focus_name"] = fname
            m.metadata["focus_pos"] = tuple(focus.position)
            role = "retreat" if outmatched else self._role(m, focus)
            m.metadata["pack_role"] = role
            if role == "engage":
                tile = self._surround_tile(m, focus, taken)
                if tile is not None:
                    taken.add(tile)
                    m.metadata["approach_pos"] = tile
        return True

    def _outmatched(self, members) -> bool:
        """The pack is losing badly — collectively hurt AND the defenders (player +
        party) clearly outweigh it. Then it pulls back to regroup (P35.2)."""
        avg = sum(m.hp / max(1, m.max_hp) for m in members) / len(members)
        if avg > 0.5:
            return False                       # still hale — press the attack
        pack = sum(m.level * (m.hp / max(1, m.max_hp)) for m in members)
        return self._defender_strength() > pack * 1.8

    def _defender_strength(self) -> float:
        engine = self.engine
        p = engine.player
        total = p.level * (p.hp / max(1, p.max_hp))
        try:
            for cid in engine.companion_manager.party:
                c = engine.npc_manager.npcs.get(cid)
                if c is not None and c.is_active():
                    total += c.level * (c.hp / max(1, c.max_hp))
        except Exception:
            pass
        return total

    def _role(self, m, focus) -> str:
        """A wounded beast RETREATS, a ranged type KITES, the rest ENGAGE."""
        if m.hp / max(1, m.max_hp) <= WOUNDED_FRAC and m is not focus:
            return "retreat"
        beh = (getattr(m, "metadata", {}) or {}).get("behavior", {}) or {}
        if beh.get("ranged") or "archer" in (m.name or "").lower():
            return "kite"
        return "engage"

    def _surround_tile(self, m, focus, taken):
        """A FREE, un-taken tile beside the focus — near, and favouring COVER so the
        pack fights from the treeline / against a wall (P35.3), not queued in the
        open."""
        from engine.squad_tactics import _NEIGHBORS, _free
        from engine import terrain_combat as tc
        wmap = self.engine.world.map
        fx, fy = focus.position
        ax, ay = m.position
        if abs(ax - fx) <= 1 and abs(ay - fy) <= 1:
            return (ax, ay)                    # already in a flanking spot — hold
        best, bscore = None, 10 ** 9
        for dx, dy in _NEIGHBORS:
            x, y = fx + dx, fy + dy
            if (x, y) in taken or not _free(wmap, x, y):
                continue
            score = (abs(x - ax) + abs(y - ay)) - tc.cover_score(self.engine, (x, y)) * 1.5
            if score < bscore:
                bscore, best = score, (x, y)
        return best

    def _focus(self, members):
        """The best target for the whole pack to gang: one it can FINISH, a
        dangerous-but-soft caster/archer, else simply the weakest reachable."""
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

        def score(t):
            s = t.hp / max(1, t.max_hp)             # softest first (the player on a tie)
            if t.hp <= FINISH_HP:
                s -= 0.6                            # gang up to FINISH the near-dead
            elif getattr(getattr(t, "character_class", None), "value", "") \
                    in _SQUISHY and s < 0.75:
                s -= 0.15                           # press a WEAKENED caster/archer
            return s
        return min(near, key=score)
