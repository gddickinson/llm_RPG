"""P32.3 neutral wildlife — a bestiary of prey (and a fox that hunts them).

The wild isn't only monsters that want the hero dead. `data/wildlife.json`
rosters NEUTRAL animals — deer, rabbit, boar, pheasant, and a red fox — that
spawn in the wilderness, WANDER and GRAZE, and FLEE the player (and, later,
predators). They never attack: an `ANIMAL`-class creature isn't a
`HOSTILE_CLASS`, so pursuit, the conflict scanner and the hostile AI all ignore
it. They ARE huntable — a felled beast drops its `loot_table` (hide/meat, via
`items.loot_tables`) and trains Hunting (P15.9b) — so the ecosystem feeds the
larder.

The predator/prey loop (a fox actually running down a rabbit; populations that
rise and fall) is P32.4; wiring hides/meat into the P16 economy is P32.5. This
layer is the living presence: something to see, and something to hunt.
"""

import logging
import random
import uuid
from typing import Optional, Tuple

from items.data_loader import load_data_dir  # noqa: F401  (kept for parity)
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.wildlife")

# terrain a wandering animal will step onto
_GRAZE_TERRAIN = (TerrainType.GRASS, TerrainType.FOREST, TerrainType.SWAMP)

SPAWN_CHANCE = 0.12       # per eligible turn, a sighting
MAX_NEARBY = 6            # don't crowd the meadow around the player
SIGHT_RADIUS = 10         # only manage animals this near the player
SPAWN_MIN = 4             # a fresh animal appears at least this far off
SPAWN_MAX = 8             # …and at most this far (out where you can watch it)
MAX_POPULATION = 24       # a hard cap so the herd never runs away (P32.4b)
BREED_CHANCE = 0.5        # a fed predator / a pair of prey may bear young
STARVE_CHANCE = 0.4       # a predator that went hungry may not see morning


def _load_roster() -> dict:
    import json
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "data", "wildlife.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as e:                       # pragma: no cover
        logger.warning(f"wildlife roster load failed: {e}")
        return {}


ROSTER = _load_roster()


def species_ids() -> list:
    return list(ROSTER.keys())


def build_wildlife(species: str, position: Tuple[int, int]):
    """Create a neutral ANIMAL Character from the roster."""
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace
    spec = ROSTER.get(species)
    if spec is None:
        raise KeyError(f"unknown wildlife species '{species}'")
    hp = spec.get("hp", 5)
    nid = f"wild_{species}_{uuid.uuid4().hex[:6]}"
    return Character(
        id=nid,
        name=spec.get("name", species.title()),
        character_class=CharacterClass.ANIMAL,
        race=CharacterRace.HUMAN,               # cosmetic; ANIMAL drives behaviour
        level=spec.get("level", 1),
        strength=8, dexterity=14, constitution=10,
        intelligence=3, wisdom=12, charisma=6,
        hp=hp, max_hp=hp,
        position=position,
        symbol=spec.get("symbol", "a"),
        description=spec.get("description", ""),
        personality={"traits": ["skittish"]},
        goals=["Graze and stay alive"],
        inventory=[],
        metadata={
            "wildlife": True,
            "species": species,
            "diet": spec.get("diet", "graze"),
            "timid": spec.get("timid", 5),
            "preys_on": spec.get("preys_on", []),
            "loot_table": spec.get("loot_table", []),
        },
    )


class WildlifeSystem:
    """Spawns and drives the neutral animal population near the player."""

    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    # ------------------------------------------------------------ helpers

    def _animals(self) -> list:
        out = []
        for npc in self.engine.npc_manager.npcs.values():
            if not (getattr(npc, "metadata", None) or {}).get("wildlife"):
                continue
            if hasattr(npc, "is_active") and not npc.is_active():
                continue
            out.append(npc)
        return out

    def _cheb(self, a, b) -> int:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    def _walkable(self, x, y) -> bool:
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return False
        if wmap.terrain[y][x] not in _GRAZE_TERRAIN:
            return False
        return (x, y) not in wmap.characters

    # --------------------------------------------------------------- tick

    def update(self) -> None:
        """One turn: spawn a sighting, then wander/flee the herd."""
        try:
            if self.engine.active_zone() is not None:
                return                          # no wildlife in dungeons/interiors
        except Exception:
            pass
        self.maybe_spawn()
        self.run_turn()

    def maybe_spawn(self) -> Optional[str]:
        if not ROSTER:
            return None
        player = self.engine.player
        if player is None:
            return None
        nearby = [a for a in self._animals()
                  if self._cheb(a.position, player.position) <= SIGHT_RADIUS]
        if len(nearby) >= MAX_NEARBY:
            return None
        if self.rng.random() > SPAWN_CHANCE:
            return None
        terrain = self.engine.world.map.get_terrain_at(*player.position)
        if terrain not in _GRAZE_TERRAIN:
            return None
        species = self._pick_for(terrain)
        if species is None:
            return None
        pos = self._spawn_pos()
        if pos is None:
            return None
        animal = build_wildlife(species, pos)
        self.engine.npc_manager.add_npc(animal)
        self.engine.world.map.place_character(animal, *pos)
        return f"You glimpse a {animal.name} in the distance."

    def _pick_for(self, terrain) -> Optional[str]:
        tv = terrain.value
        pool = [(sid, s.get("weight", 3)) for sid, s in ROSTER.items()
                if tv in s.get("terrain", [])]
        if not pool:
            return None
        total = sum(w for _, w in pool)
        r = self.rng.uniform(0, total)
        upto = 0.0
        for sid, w in pool:
            upto += w
            if r <= upto:
                return sid
        return pool[-1][0]

    def _spawn_pos(self) -> Optional[Tuple[int, int]]:
        px, py = self.engine.player.position
        for _ in range(24):
            r = self.rng.randint(SPAWN_MIN, SPAWN_MAX)
            ang = self.rng.uniform(0, 6.283)
            import math
            x = int(px + r * math.cos(ang))
            y = int(py + r * math.sin(ang))
            if self._walkable(x, y):
                return (x, y)
        return None

    def run_turn(self) -> None:
        player = self.engine.player
        ppos = player.position if player else None
        for animal in self._animals():
            if ppos and self._cheb(animal.position, ppos) > SIGHT_RADIUS:
                continue                        # off-screen animals idle (cheap)
            self._act(animal, ppos)

    def _act(self, animal, ppos) -> None:
        meta = animal.metadata
        timid = meta.get("timid", 5)
        # the hero always spooks a wild thing first — bolt from a person
        if ppos and self._cheb(animal.position, ppos) <= timid:
            self._flee(animal, ppos)
            return
        # P32.4: prey flees a nearby PREDATOR too; a predator hunts its prey
        threat = self._nearest_predator(animal)
        if threat is not None:
            self._flee(animal, threat.position)
            return
        if meta.get("preys_on"):
            if self._hunt(animal):
                return                          # closed on / caught a meal
        if self.rng.random() < 0.5:
            self._wander(animal)                # otherwise graze/amble

    def _nearest_predator(self, prey):
        """The closest live predator that eats this prey's species, within the
        prey's timid radius (P32.4)."""
        species = (prey.metadata or {}).get("species")
        timid = (prey.metadata or {}).get("timid", 5)
        best, bestd = None, timid + 1
        for other in self._animals():
            if other is prey:
                continue
            if species not in (other.metadata or {}).get("preys_on", []):
                continue
            d = self._cheb(prey.position, other.position)
            if d <= timid and d < bestd:
                best, bestd = other, d
        return best

    def _hunt(self, predator) -> bool:
        """A predator steps toward the nearest prey it eats; adjacent, it makes
        the kill (P32.4). Returns True if it acted on a hunt."""
        preys = predator.metadata.get("preys_on", [])
        hunt_r = SIGHT_RADIUS
        target, td = None, hunt_r + 1
        for other in self._animals():
            if other is predator:
                continue
            if (other.metadata or {}).get("species") not in preys:
                continue
            d = self._cheb(predator.position, other.position)
            if d < td:
                target, td = other, d
        if target is None:
            return False
        if td <= 1:
            self._make_kill(predator, target)
            return True
        self._step_toward(predator, target.position)
        return True

    def _make_kill(self, predator, prey) -> None:
        predator.metadata["fed"] = True         # fed today (feeds P32.4b breeding)
        self.engine.world.map.remove_character(prey)
        self.engine.npc_manager.remove_npc(prey.id)
        try:                                    # only report a kill you could see
            if self._cheb(predator.position, self.engine.player.position) <= 8:
                self.engine.memory_manager.add_event(
                    f"A {predator.name} runs down a {prey.name}.")
        except Exception:
            pass

    def _step_toward(self, animal, target) -> None:
        x, y = animal.position
        sx = (target[0] > x) - (target[0] < x)
        sy = (target[1] > y) - (target[1] < y)
        for mvx, mvy in ((sx, sy), (sx, 0), (0, sy)):
            if mvx == 0 and mvy == 0:
                continue
            nx, ny = x + mvx, y + mvy
            if (nx, ny) == tuple(target):
                continue                        # its own move lands the kill
            if self._walkable(nx, ny):
                self.engine.world.map.move_character(animal, nx, ny)
                return

    def _flee(self, animal, ppos) -> None:
        x, y = animal.position
        dx = (x - ppos[0])
        dy = (y - ppos[1])
        sx = (dx > 0) - (dx < 0)
        sy = (dy > 0) - (dy < 0)
        for mvx, mvy in ((sx, sy), (sx, 0), (0, sy)):
            if mvx == 0 and mvy == 0:
                continue
            if self._walkable(x + mvx, y + mvy):
                self.engine.world.map.move_character(animal, x + mvx, y + mvy)
                return

    def _wander(self, animal) -> None:
        x, y = animal.position
        mvx = self.rng.randint(-1, 1)
        mvy = self.rng.randint(-1, 1)
        if (mvx or mvy) and self._walkable(x + mvx, y + mvy):
            self.engine.world.map.move_character(animal, x + mvx, y + mvy)

    # ------------------------------------------------------- nightly pass

    def run_day(self) -> None:
        """P32.4b population dynamics (nightly, cheap): a predator that ATE
        breeds and a starving one dies; prey with company breed. Capped so the
        living herd rises and falls instead of exploding or dying out."""
        animals = self._animals()
        by_species = {}
        for a in animals:
            by_species.setdefault((a.metadata or {}).get("species"), []).append(a)
        pop = len(animals)
        for a in list(animals):
            meta = a.metadata or {}
            if meta.get("preys_on"):                     # a PREDATOR
                if meta.pop("fed", False):
                    if pop < MAX_POPULATION and self.rng.random() < BREED_CHANCE:
                        if self._breed(a):
                            pop += 1
                elif self.rng.random() < STARVE_CHANCE:  # went hungry — it dies
                    self.engine.world.map.remove_character(a)
                    self.engine.npc_manager.remove_npc(a.id)
                    pop -= 1
        for species, herd in by_species.items():         # PREY breed with company
            if not species or ROSTER.get(species, {}).get("preys_on"):
                continue
            if len(herd) >= 2 and pop < MAX_POPULATION and \
                    self.rng.random() < BREED_CHANCE:
                if self._breed(herd[0]):
                    pop += 1

    def _breed(self, parent) -> bool:
        """Spawn one offspring of the parent's species on a free tile beside
        it. Returns True if a calf/kit was born."""
        species = (parent.metadata or {}).get("species")
        if species not in ROSTER:
            return False
        px, py = parent.position
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if self._walkable(px + dx, py + dy):
                    calf = build_wildlife(species, (px + dx, py + dy))
                    self.engine.npc_manager.add_npc(calf)
                    self.engine.world.map.place_character(calf, px + dx, py + dy)
                    return True
        return False
