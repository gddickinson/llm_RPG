"""P35.3 terrain & cover in live combat.

The ground matters: fighting from FOREST/RUBBLE or hugging a wall gives COVER (worth
more against arrows than a blade in your face); swinging hand-to-hand while standing
in WATER/MARSH is treacherous (an off-balance penalty); an archer on HIGH GROUND (up
on the rocks) looses down with an edge. Pure over (engine, positions); applied in
`combat_system._resolve` and read by the pack AI so monsters use cover to advantage.
"""

from world.world_map import TerrainType as T

# terrain you STAND in that shields you
_COVER_IN = {T.FOREST: 2, T.RUBBLE: 2, T.SWAMP: 1}
# terrain BESIDE you that you can put at your back
_COVER_ADJ = {T.BUILDING: 3, T.MOUNTAIN: 2, T.RUBBLE: 1}
# treacherous footing for hand-to-hand
_DIFFICULT = (T.WATER, T.SWAMP)
_DIRS8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def terrain_at(engine, pos):
    try:
        return engine.world.map.get_terrain_at(pos[0], pos[1])
    except Exception:
        return None


def _beside(engine, pos, kinds):
    x, y = pos
    best = 0
    for dx, dy in _DIRS8:
        t = terrain_at(engine, (x + dx, y + dy))
        if t in kinds:
            best = max(best, kinds[t])
    return best


def cover_ac(engine, defender, ranged=False) -> int:
    """The defender's cover bonus. Cover from the forest / a wall shields you MORE
    from a shot than from a blade at arm's length."""
    pos = getattr(defender, "position", None)
    if pos is None:
        return 0
    ac = max(_COVER_IN.get(terrain_at(engine, pos), 0),
             _beside(engine, pos, _COVER_ADJ))
    if ac <= 0:
        return 0
    return ac + 1 if ranged else ac // 2


def footing_penalty(engine, attacker, action_type) -> int:
    """A hand-to-hand attacker standing in water/marsh swings off-balance."""
    if action_type in ("shoot", "cast"):
        return 0
    return 2 if terrain_at(engine, getattr(attacker, "position", (0, 0))) \
        in _DIFFICULT else 0


def high_ground(engine, attacker, defender, action_type) -> int:
    """An archer up on the rocks (beside a mountain) firing at someone on the flat
    below gets the high-ground edge."""
    if action_type not in ("shoot", "cast"):
        return 0
    up = _beside(engine, getattr(attacker, "position", (0, 0)), {T.MOUNTAIN: 1})
    down = _beside(engine, getattr(defender, "position", (0, 0)), {T.MOUNTAIN: 1})
    return 2 if (up and not down) else 0


def to_hit_mod(engine, attacker, defender, action_type) -> int:
    """Net terrain to-hit modifier for the attacker (+high ground, −bad footing)."""
    return (high_ground(engine, attacker, defender, action_type)
            - footing_penalty(engine, attacker, action_type))


def cover_score(engine, pos) -> int:
    """How much cover a tile offers (for the AI choosing where to fight)."""
    return max(_COVER_IN.get(terrain_at(engine, pos), 0),
               _beside(engine, pos, _COVER_ADJ))
