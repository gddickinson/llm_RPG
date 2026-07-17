"""The COLOSSEUM — a staging arena for combat between two or more opponents
(George, inspired by autonomous_world's colosseum).

A simple, controlled environment for TESTING combat: stage a matchup (a duel, a
team skirmish, a beast brawl) of real game Characters in a walled sand arena and
watch them fight with the FULL combat pipeline — the same `combat_system` d20
strikes, the pack/positional TACTICS, and the character GRAPHICS + animations
(attack swings, hurt recoils, deaths, the iso body render) — so you can see how
the combat + its graphics actually read. Two teams spawn at opposite ends, each
fighter driven every tick to close on and cut down the nearest enemy; the last
team standing wins.

Content (matchups + arena size) lives in `data/colosseum.json`. Fighters are
tagged `metadata["arena_fighter"]` so the ordinary NPC AI / pursuit / conflict
leave them to the arena. State: the arena rect persists; a live fight is
transient (not saved).
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.colosseum")

# ranged / caster callings pick a shot or a spell instead of a melee swing
_RANGED = {"ranger", "archer"}
_CASTER = {"wizard", "sorcerer", "warlock", "druid"}


def is_fighter(char) -> bool:
    """True for a character currently staged in the arena (the ordinary AI, the
    pursuit + aggression + conflict systems all skip these)."""
    return bool((getattr(char, "metadata", None) or {}).get("arena_fighter"))


class ColosseumSystem:
    def __init__(self, engine):
        self.engine = engine
        self.arena = None            # (x0, y0, x1, y1) or None until seeded
        self.fighter_ids = []        # live fighter ids
        self.active = False
        self.result = None           # None | "team_a" | "team_b" | "draw"
        self.matchup_name = ""
        self._last = ""
        self._data = _load()

    # -------------------------------------------------------------- content
    def matchups(self):
        """[(id, name, desc)] for the pick-a-fight menu."""
        return [(m["id"], m.get("name", m["id"]), m.get("desc", ""))
                for m in self._data.get("matchups", [])]

    def _matchup(self, preset_id):
        for m in self._data.get("matchups", []):
            if m["id"] == preset_id:
                return m
        return None

    # -------------------------------------------------------------- arena
    def seed(self):
        """Plant the arena: a flat sand ring on a CLEAR patch of grass near the
        player start (never clobbering forests, water, buildings or the features
        other systems seed), walled with a gate + a `Colosseum` Location marker.
        Returns the arena rect (or None if no clear patch was found)."""
        eng = self.engine
        wmap = eng.world.map
        aw = self._data.get("arena", {}).get("width", 18)
        ah = self._data.get("arena", {}).get("height", 12)
        px, py = eng.player.position if eng.player else (wmap.width // 2,
                                                         wmap.height // 2)
        spot = self._find_clear_rect(wmap, aw, ah, px, py)
        if spot is None:
            logger.info("Colosseum: no clear ground for an arena")
            return None
        x0, y0 = spot
        self.arena = (x0, y0, x0 + aw - 1, y0 + ah - 1)
        self._lay_arena()
        self._plant_marker()
        return self.arena

    @staticmethod
    def _find_clear_rect(wmap, aw, ah, px, py):
        """The nearest top-left where an aw×ah rect is ALL plain grass (so the
        arena stamp disturbs nothing)."""
        from world.world_map import TerrainType
        grass = TerrainType.GRASS

        def clear(x0, y0):
            if x0 < 2 or y0 < 2 or x0 + aw > wmap.width - 2 \
                    or y0 + ah > wmap.height - 2:
                return False
            for y in range(y0, y0 + ah):
                for x in range(x0, x0 + aw):
                    if wmap.terrain[y][x] != grass:
                        return False
            return True

        # spiral out from a point a little east of the player
        cx, cy = px + 6 + aw // 2, py
        for r in range(0, max(wmap.width, wmap.height)):
            for dx in range(-r, r + 1):
                for dy in (-r, r) if abs(dx) != r else range(-r, r + 1):
                    x0, y0 = cx + dx - aw // 2, cy + dy - ah // 2
                    if clear(x0, y0):
                        return (x0, y0)
        return None

    def _lay_arena(self):
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        x0, y0, x1, y1 = self.arena
        sand = TerrainType.ROAD                          # packed-earth arena floor
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                edge = x in (x0, x1) or y in (y0, y1)
                gate = edge and x == x0 and y == (y0 + y1) // 2
                if edge and not gate:
                    wmap.terrain[y][x] = TerrainType.BUILDING   # the ring wall
                else:
                    wmap.terrain[y][x] = sand
                ch = wmap.get_character_at(x, y)
                if ch is not None and ch is not self.engine.player:
                    try:
                        wmap.remove_character(ch)
                    except Exception:
                        pass

    def _plant_marker(self):
        from world.location import Location
        x0, y0, x1, y1 = self.arena
        gx, gy = x0, (y0 + y1) // 2
        try:
            loc = Location("The Colosseum", x=gx, y=gy, width=1, height=1)
            loc.set_property("type", "colosseum")
            loc.set_property("colosseum", True)
            self.engine.world.locations.append(loc)
        except Exception as e:
            logger.debug(f"colosseum marker failed: {e}")

    def at_entrance(self, pos) -> bool:
        """Is `pos` on / beside the arena gate (so E opens the pick-a-fight menu)?"""
        if not self.arena:
            return False
        x0, y0, x1, y1 = self.arena
        gx, gy = x0, (y0 + y1) // 2
        return abs(pos[0] - gx) <= 1 and abs(pos[1] - gy) <= 1

    # -------------------------------------------------------------- staging
    def stage(self, preset_id) -> bool:
        """Spawn a matchup's two teams at opposite ends of the arena and begin."""
        m = self._matchup(preset_id)
        if m is None or not self.arena:
            return False
        self.clear()
        x0, y0, x1, y1 = self.arena
        level = int(m.get("level", 3))
        a_col, b_col = x0 + 3, x1 - 3
        self._spawn_team(m.get("team_a", []), 0, a_col, y0, y1, level)
        self._spawn_team(m.get("team_b", []), 1, b_col, y0, y1, level)
        self.active = True
        self.result = None
        self._last = preset_id
        self.matchup_name = m.get("name", preset_id)
        self.engine.memory_manager.add_event(
            f"[Arena] The {self.matchup_name} begins!")
        return bool(self.fighter_ids)

    def enter(self, preset_id=None) -> bool:
        """Seat the player as a SPECTATOR at the arena gate (revealing the ring)
        and stage a matchup — the `--colosseum` entry + the E-key hook."""
        if not self.arena:
            self.seed()
        if not self.arena:
            return False
        x0, y0, x1, y1 = self.arena
        p = self.engine.player
        wmap = self.engine.world.map
        gx, gy = x0 - 1, (y0 + y1) // 2
        try:
            wmap.remove_character(p)
        except Exception:
            pass
        p.position = (gx, gy)
        try:
            wmap.place_character(p, gx, gy)
        except Exception:
            pass
        explored = p.metadata.setdefault("explored", set())
        for yy in range(y0 - 2, y1 + 3):
            for xx in range(x0 - 2, x1 + 3):
                explored.add((xx, yy))
        return self.stage(preset_id) if preset_id else self.stage_next()

    def stage_next(self) -> bool:
        """Stage the NEXT matchup in the list (cycles) — the E-key at the arena
        runs this so a spectator can flick through the fights."""
        ids = [m["id"] for m in self._data.get("matchups", [])]
        if not ids:
            return False
        i = (ids.index(self._last) + 1) % len(ids) if self._last in ids else 0
        return self.stage(ids[i])

    def _spawn_team(self, roster, team, col, y0, y1, level):
        slots = []
        for entry in roster:
            slots += [entry.get("type", "warrior")] * int(entry.get("count", 1))
        n = len(slots)
        top = (y0 + y1) // 2 - n // 2
        for i, kind in enumerate(slots):
            row = max(y0 + 1, min(y1 - 1, top + i))
            self._spawn_fighter(kind, (col, row), team, level)

    def _spawn_fighter(self, kind, pos, team, level):
        eng = self.engine
        fighter = _make_fighter(eng, kind, pos, level)
        if fighter is None:
            return
        fighter.position = pos
        md = fighter.metadata
        md["arena_fighter"] = True
        md["arena_team"] = team
        eng.npc_manager.add_npc(fighter)
        try:
            eng.world.map.place_character(fighter, *pos)
        except Exception:
            pass
        self.fighter_ids.append(fighter.id)

    # -------------------------------------------------------------- the fight
    def run_turn(self):
        """Drive one round: every living fighter closes on and strikes the
        nearest enemy (the real combat_system). Called from the turn pipeline."""
        if not self.active:
            return
        fighters = [self.engine.npc_manager.npcs.get(fid)
                    for fid in self.fighter_ids]
        living = [f for f in fighters if f is not None and f.is_alive()]
        for f in living:
            if not f.is_alive():
                continue
            enemy = self._nearest_enemy(f, living)
            if enemy is None:
                continue
            self._act(f, enemy)
        if self.over:
            self._finish()

    def _act(self, f, enemy):
        klass = getattr(getattr(f, "character_class", None), "value", "")
        dx = enemy.position[0] - f.position[0]
        dy = enemy.position[1] - f.position[1]
        adj = dx * dx + dy * dy <= 3
        # a melee fighter occasionally raises a GUARD or DODGES instead of
        # striking — a defensive beat (deterministic, ~1 in 6 turns) so the
        # block / crouch-block / dodge animations show in a real bout
        if adj and klass not in _CASTER and klass not in _RANGED and \
                (hash(f.id) + self.engine.turn_counter) % 6 == 0:
            h = hash(f.id) // 6
            f.metadata["_emote"] = ("dodge", "block", "crouch_block")[h % 3]
            return
        if klass in _CASTER and self._has_mana(f):
            action = "cast"
        elif klass in _RANGED:
            action = "shoot"
        else:
            action = "attack"
        try:
            self.engine.combat_system.npc_attack(f, enemy.name, action)
        except Exception as e:
            logger.debug(f"arena act failed: {e}")

    def _nearest_enemy(self, f, living):
        team = (f.metadata or {}).get("arena_team")
        fx, fy = f.position
        best, bd = None, 1e9
        for o in living:
            if o is f or (o.metadata or {}).get("arena_team") == team:
                continue
            d = (o.position[0] - fx) ** 2 + (o.position[1] - fy) ** 2
            if d < bd:
                best, bd = o, d
        return best

    @staticmethod
    def _has_mana(f):
        return int((getattr(f, "metadata", None) or {}).get("mana",
                   getattr(f, "mana", 1)) or 0) > 0

    # -------------------------------------------------------------- result
    @property
    def over(self) -> bool:
        if not self.active:
            return False
        return self._living(0) == 0 or self._living(1) == 0

    def _living(self, team) -> int:
        n = 0
        for fid in self.fighter_ids:
            f = self.engine.npc_manager.npcs.get(fid)
            if f is not None and f.is_alive() and \
                    (f.metadata or {}).get("arena_team") == team:
                n += 1
        return n

    def winner(self):
        a, b = self._living(0), self._living(1)
        return "team_a" if a and not b else "team_b" if b and not a \
            else "draw" if not a and not b else None

    def _finish(self):
        self.active = False
        self.result = self.winner()
        side = {"team_a": "Team A", "team_b": "Team B"}.get(self.result, "No one")
        self.engine.memory_manager.add_event(
            f"[Arena] {side} wins the {self.matchup_name}!")

    def clear(self):
        """Remove any staged fighters and reset the arena for a fresh matchup."""
        for fid in self.fighter_ids:
            f = self.engine.npc_manager.npcs.pop(fid, None)
            if f is not None:
                try:
                    self.engine.world.map.remove_character(f)
                except Exception:
                    pass
        self.fighter_ids = []
        self.active = False
        self.result = None

    # -------------------------------------------------------------- persist
    def to_dict(self):
        return {"arena": self.arena}

    def from_dict(self, d):
        if d:
            a = d.get("arena")
            self.arena = tuple(a) if a else None


# ------------------------------------------------------------------ helpers
def _load():
    try:
        with open(os.path.join("data", "colosseum.json")) as fp:
            return json.load(fp)
    except Exception as e:
        logger.warning(f"colosseum.json missing/broken: {e}")
        return {"arena": {"width": 18, "height": 12}, "matchups": []}


_MONSTER_IDS = None


def _is_monster(kind) -> bool:
    global _MONSTER_IDS
    if _MONSTER_IDS is None:
        try:
            with open(os.path.join("data", "monsters.json")) as fp:
                data = json.load(fp)
            _MONSTER_IDS = set(data.keys()) if isinstance(data, dict) else \
                {m.get("id") for m in data}
        except Exception:
            _MONSTER_IDS = set()
    return kind in _MONSTER_IDS


def _make_fighter(engine, kind, pos, level):
    """A monster template → build_monster; else a class → a fresh NPC. Buffed a
    little so the bout lasts long enough to watch."""
    fighter = None
    if _is_monster(kind):
        try:
            from world.monsters import build_monster
            fighter = build_monster(kind, pos)
        except Exception:
            fighter = None
    if fighter is None:
        try:
            from characters.character_types import CharacterClass
            klass = CharacterClass(kind)
            fighter = engine.npc_manager.create_random_npc(char_class=klass)
        except Exception:
            return None
    if fighter is None:
        return None
    try:
        fighter.level = max(1, int(level))
        base = int(getattr(fighter, "max_hp", 20) or 20)
        fighter.max_hp = int(base * 1.4) + level * 6
        fighter.hp = fighter.max_hp
    except Exception:
        pass
    return fighter
