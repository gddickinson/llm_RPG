"""LIVING_WORLD Area B — wildlife ETHOLOGY (pure behaviour, split from wildlife.py).

The audit finding: absent a nearby player/predator, every animal was a 50/50
stand-or-random-step wanderer — no sleep, no seeking food or water, no herd. This
layer gives the herd a real day: it BEDS DOWN at its rest time (B1 day/night),
GRAZES toward its diet terrain and DRINKS at water on a hunger/thirst drive (B2),
and drifts as a HERD (B3 boids-lite cohesion) instead of jittering. `WildlifeSystem
._act` calls `live()` after its survival/hunt checks; everything here is pure over
the animal's metadata + the system's map helpers (`_walkable`/`_wander`/`_animals`).
"""

from engine import anim
from world.world_map import TerrainType

# B2 diet → the terrain a species FEEDS on; water it DRINKS from
_DIET_TERRAIN = {
    "graze": (TerrainType.GRASS, TerrainType.FOREST),   # meadow/woodland grazers
    "root": (TerrainType.SWAMP, TerrainType.FOREST),    # rooters
}
_WATER = (TerrainType.WATER,)
_ADJ = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))

THIRST_SEEK = 8           # turns before an animal goes looking for water
HUNGER_SEEK = 3           # ... and before a grazer stops to feed
WATER_RANGE = 6           # how far it will spot water / food
FOOD_RANGE = 5
HERD_RADIUS = 5           # B3 herd cohesion range
HERD_BIAS = 0.7           # chance a herd animal moves WITH the herd vs a free amble


def _sign(v) -> int:
    return (v > 0) - (v < 0)


# ------------------------------------------------------------- B1 day/night
def is_night(engine) -> bool:
    try:
        return engine.world.get_time_of_day() == "night"
    except Exception:
        return False


def is_rest_time(meta, night) -> bool:
    """A DIURNAL animal (default) rests at night; a NOCTURNAL one by day."""
    active = meta.get("active", "day")
    return night if active == "day" else not night


# ------------------------------------------------------------- the day
def live(sys, animal, night) -> None:
    """One turn of an animal's own life (after the survival/hunt checks): rest at
    its off-hour, else drink / graze on a drive, else drift with the herd."""
    meta = animal.metadata
    if is_rest_time(meta, night):
        _rest(sys, animal)
        return
    _wake(animal)
    meta["thirst"] = meta.get("thirst", 0) + 1
    if meta["thirst"] >= THIRST_SEEK and _seek_water(sys, animal):
        return
    if meta.get("diet") in ("graze", "root"):
        meta["hunger"] = meta.get("hunger", 0) + 1
        if meta["hunger"] >= HUNGER_SEEK and _feed(sys, animal):
            return
    _herd_amble(sys, animal)


def _rest(sys, animal) -> None:
    """Bed down: stay put and show a sleep bubble (survival still overrides — the
    flee checks in `_act` run first, so an approaching player wakes it)."""
    meta = animal.metadata
    meta["asleep"] = True
    try:
        anim.bubble(animal, "sleep")
    except Exception:
        pass


def _wake(animal) -> None:
    if animal.metadata.pop("asleep", None):
        animal.metadata.pop("_bubble", None)


# ------------------------------------------------------------- B2 drink / graze
def _seek_water(sys, animal) -> bool:
    x, y = animal.position
    wmap = sys.engine.world.map
    for dx, dy in _ADJ:                        # adjacent water → drink
        if _terrain_is(wmap, x + dx, y + dy, _WATER):
            animal.metadata["thirst"] = 0
            _peck(animal)
            return True
    target = _nearest_terrain(sys, animal, _WATER, WATER_RANGE)
    if target is not None:
        return _step_to(sys, animal, target)   # walk to the water's edge
    return False


def _feed(sys, animal) -> bool:
    diet = animal.metadata.get("diet", "graze")
    food = _DIET_TERRAIN.get(diet, (TerrainType.GRASS,))
    wmap = sys.engine.world.map
    x, y = animal.position
    if wmap.terrain[y][x] in food:             # on good ground → graze (a pause)
        animal.metadata["hunger"] = 0
        _peck(animal)
        return True
    target = _nearest_terrain(sys, animal, food, FOOD_RANGE)
    if target is not None:
        return _step_to(sys, animal, target)
    return False


def _peck(animal) -> None:
    try:
        anim.emote(animal, "stoop")            # head down to graze / drink
    except Exception:
        pass


# ------------------------------------------------------------- B3 herding
def _herd_amble(sys, animal) -> None:
    v = _herd_vector(sys, animal)
    x, y = animal.position
    if v != (0, 0) and sys.rng.random() < HERD_BIAS:
        nx, ny = x + v[0], y + v[1]
        if sys._walkable(nx, ny):
            sys.engine.world.map.move_character(animal, nx, ny)
            return
    sys._wander(animal)                        # solitary / no cohesion → free amble


def _herd_vector(sys, animal):
    """Boids-lite: a step toward the same-species herd centroid (cohesion) minus a
    nudge off any herdmate crowded right against us (separation). (0,0) = alone."""
    species = (animal.metadata or {}).get("species")
    x, y = animal.position
    cx = cy = n = 0
    sepx = sepy = 0
    for other in sys._animals():
        if other is animal or (other.metadata or {}).get("species") != species:
            continue
        ox, oy = other.position
        d = max(abs(ox - x), abs(oy - y))
        if d > HERD_RADIUS:
            continue
        cx += ox
        cy += oy
        n += 1
        if d <= 1:
            sepx += (x - ox)
            sepy += (y - oy)
    if n == 0:
        return (0, 0)
    vx = (cx / n - x) + sepx
    vy = (cy / n - y) + sepy
    return (_sign(vx), _sign(vy))


# ------------------------------------------------------------- map helpers
def _terrain_is(wmap, x, y, kinds) -> bool:
    return 0 <= x < wmap.width and 0 <= y < wmap.height and \
        wmap.terrain[y][x] in kinds


def _nearest_terrain(sys, animal, kinds, radius):
    wmap = sys.engine.world.map
    x, y = animal.position
    best, bd = None, radius + 1
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d = max(abs(dx), abs(dy))
            if d == 0 or d >= bd:
                continue
            if _terrain_is(wmap, x + dx, y + dy, kinds):
                best, bd = (x + dx, y + dy), d
    return best


def _step_to(sys, animal, target) -> bool:
    x, y = animal.position
    sx, sy = _sign(target[0] - x), _sign(target[1] - y)
    for mvx, mvy in ((sx, sy), (sx, 0), (0, sy)):
        if mvx == 0 and mvy == 0:
            continue
        if sys._walkable(x + mvx, y + mvy):
            sys.engine.world.map.move_character(animal, x + mvx, y + mvy)
            return True
    return False


# ------------------------------------------------------------- C5 predation
def monster_predation(sys, ppos) -> None:
    """A predatory MONSTER (a wolf, a bog lurker — `preys_on` in
    data/monsters.json) that isn't busy with the player runs down the nearest
    wildlife it eats — the world's predators join the food web. Sets `_aggro_turn`
    so the ambient AI doesn't also move it this turn (wildlife runs before
    `process_npc_turns`). Called from `WildlifeSystem.run_turn`."""
    if ppos is None:
        return
    from world.wildlife import SIGHT_RADIUS
    prey = [a for a in sys._animals()
            if sys._cheb(a.position, ppos) <= SIGHT_RADIUS]
    if not prey:
        return
    turn = getattr(sys.engine, "turn_counter", 0)
    for m in list(sys.engine.npc_manager.npcs.values()):
        meta = m.metadata or {}
        if not meta.get("preys_on") or meta.get("wildlife") or not m.is_alive():
            continue
        d_player = sys._cheb(m.position, ppos)
        if d_player > SIGHT_RADIUS or d_player <= 2:     # far off, or on the hero
            continue
        target, td = None, SIGHT_RADIUS + 1
        for a in prey:
            if (a.metadata or {}).get("species") in meta["preys_on"] and \
                    a.is_alive():
                d = sys._cheb(m.position, a.position)
                if d < td:
                    target, td = a, d
        if target is None:
            continue
        if td <= 1:
            sys._make_kill(m, target)
        else:
            sys._step_toward(m, target.position)
        meta["_aggro_turn"] = turn                        # skip the ambient AI
