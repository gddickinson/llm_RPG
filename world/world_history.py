"""P36.3 deep-history world simulation (adapted from autonomous_world/history_sim).

Runs at realistic-world creation: over simulated CENTURIES, peoples found
settlements at suitable sites (`river_gen.score_site`), rival realms go to WAR and
raze some to RUINS, and the survivors lay ROADS between them. It returns the ruins to
place on the map and a dated CHRONICLE the Y-journal shows — so a realistic world has
a visible PAST (broken towers, sunken halls, old battlefields) and a written history.
Pure over the terrain grid; no engine, no LLM. Lean adaptation, not a port.
"""

import random
from dataclasses import dataclass

from world.world_map import TerrainType as T

_PEOPLES = ("the Ashfolk", "the Vael elves", "the Karrûn dwarves",
            "the Marshmen", "the Sunward realm", "the Iron confederacy",
            "the Hill clans")
_NAMES = ("Duncar", "Elenmoor", "Karrathal", "Whitmere", "Dunhollow",
          "Ravenfell", "Thornkeep", "Greymouth", "Oldwick", "Fenwatch",
          "Stonebridge", "Ashford", "Highcairn", "Merrowdale", "Bramblewood")
_RUINS = (("ancient ruins", "the tumbled stones of {n}, an age gone"),
          ("a ruined tower", "the broken tower of {n}"),
          ("an abandoned mine", "the flooded workings under {n}"),
          ("a sunken hall", "the drowned hall of {n}"),
          ("an old battlefield", "the barrow-field where {n} made its last stand"))
_LAND = (T.GRASS, T.FOREST)


@dataclass
class Ruin:
    name: str
    x: int
    y: int
    kind: str
    legend: str
    year: int


def _sites(terrain, rng, n):
    """Suitable, spaced-apart land sites, best (score_site) first."""
    from world.river_gen import score_site
    h, w = len(terrain), len(terrain[0])
    cands = []
    for _ in range(n * 12):
        x, y = rng.randint(3, w - 4), rng.randint(3, h - 4)
        if terrain[y][x] in _LAND:
            cands.append((score_site(terrain, x, y), x, y))
    cands.sort(key=lambda c: -c[0])
    picked = []
    for _s, x, y in cands:
        if all(abs(x - px) + abs(y - py) > 9 for px, py in picked):
            picked.append((x, y))
        if len(picked) >= n:
            break
    return picked


def simulate(terrain, seed, max_settlements=8):
    """→ dict(settlements, ruins, roads, chronicle) from a centuries-long sim."""
    rng = random.Random(seed ^ 0x51573)
    sites = _sites(terrain, rng, max_settlements + 4)
    names = list(_NAMES)
    rng.shuffle(names)
    settlements, chronicle, year = [], [], rng.randint(20, 60)
    for (x, y) in sites:
        if not names:
            break
        year += rng.randint(20, 70)
        s = {"name": names.pop(), "x": x, "y": y,
             "race": rng.choice(_PEOPLES), "founded": year}
        settlements.append(s)
        chronicle.append(f"Year {year}: {s['race']} founded {s['name']}.")

    survivors, ruins = settlements[:], []
    for _ in range(max(1, len(settlements) // 3)):
        if len(survivors) < 2:
            break
        year += rng.randint(30, 90)
        atk = rng.choice(survivors)
        rivals = [s for s in survivors if s["race"] != atk["race"]]
        if not rivals:
            continue
        victim = min(rivals, key=lambda s: abs(s["x"] - atk["x"])
                     + abs(s["y"] - atk["y"]))
        survivors.remove(victim)
        kind, tmpl = rng.choice(_RUINS)
        ruins.append(Ruin(victim["name"], victim["x"], victim["y"], kind,
                          tmpl.format(n=victim["name"]), year))
        chronicle.append(f"Year {year}: {atk['race']} razed {victim['name']} "
                         f"— now {kind}.")

    roads = []
    for a in survivors:
        others = [b for b in survivors if b is not a]
        if others:
            b = min(others, key=lambda b: abs(b["x"] - a["x"])
                    + abs(b["y"] - a["y"]))
            roads.append(((a["x"], a["y"]), (b["x"], b["y"])))
    if survivors:
        chronicle.append(f"By year {year}, {len(survivors)} settlements endured, "
                         f"bound by road; {len(ruins)} lay in ruin.")
    return {"settlements": survivors, "ruins": ruins, "roads": roads,
            "chronicle": chronicle}
