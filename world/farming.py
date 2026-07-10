"""Crops (P8.3, ported from autonomous_world's crop_system).

Farmland visibly lives by the calendar: each farm location gets a
small field that runs fallow → planted (spring) → growing → mature →
harvested, with growth speed driven by the astronomy port's solar
intensity — long bright summers ripen fields fast, grey ones drag.

The player can harvest a mature field tile (the normal Z forage key)
for wheat sheaves; whatever stands unharvested when autumn ends is
brought in by the farmers — village stores rise in the faction ticker
and the harvest enters the rumor mill. Winter turns everything fallow
again. Plot state persists via save_load.

The grazing half of the AW module is deferred: this world has no
herbivore wildlife yet (see DEVELOPMENT_PLAN P8.3 note).
"""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("llm_rpg.farming")

PLOT_W, PLOT_H = 4, 3
SPROUT_DAYS = 5             # planted -> growing
BASE_RIPEN_DAYS = 22        # growing -> mature at zero sun
SUN_RIPEN_CUT = 10          # ... minus up to this many days of full sun
CROP_ITEM = "wheat_sheaf"
HARVEST_STORES = 6          # village stores per farm the farmers bring in


class FarmManager:
    def __init__(self, engine):
        self.engine = engine
        # (x, y) -> {"state": str, "since": day}
        self.plots: Dict[Tuple[int, int], Dict] = {}
        self._announced: Dict[str, int] = {}

    # -------------------------------------------------------- world setup

    def ensure_plots(self) -> int:
        """Claim a field of grass beside every farm location (once)."""
        if self.plots:
            return 0
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        claimed = 0
        for loc in self.engine.world.locations:
            if "farm" not in loc.name.lower():
                continue
            fx = min(loc.x + loc.width + 1, wmap.width - PLOT_W - 1)
            fy = min(loc.y, wmap.height - PLOT_H - 1)
            for y in range(fy, fy + PLOT_H):
                for x in range(fx, fx + PLOT_W):
                    if wmap.get_terrain_at(x, y) == TerrainType.GRASS:
                        wmap.terrain[y][x] = TerrainType.FARMLAND
                        self.plots[(x, y)] = {"state": "fallow",
                                              "since": self._day()}
                        claimed += 1
        if claimed:
            logger.info(f"Farms: claimed {claimed} field tiles")
        return claimed

    # ------------------------------------------------------------ daily

    def run_day(self) -> None:
        if not self.plots:
            return
        day = self._day()
        try:
            season = self.engine.world.get_date().season.value
        except Exception:
            season = "summer"
        try:
            from world.astronomy import solar_intensity, YEAR_LENGTH
            sun = solar_intensity(day % YEAR_LENGTH)
        except Exception:
            sun = 0.7
        ripen_days = int(BASE_RIPEN_DAYS - SUN_RIPEN_CUT * sun)
        farmers_took = 0
        for pos, plot in self.plots.items():
            state, since = plot["state"], plot["since"]
            if season == "winter":
                if state != "fallow":
                    plot.update(state="fallow", since=day)
                continue
            if state == "fallow" and season == "spring":
                plot.update(state="planted", since=day)
                self._announce("planting", day,
                               "Planting has begun in the fields.")
            elif state == "planted" and day - since >= SPROUT_DAYS:
                plot.update(state="growing", since=day)
            elif state == "growing" and day - since >= ripen_days:
                plot.update(state="mature", since=day)
                self._announce("ripe", day,
                               "The fields stand golden — harvest "
                               "time is here.")
            elif state == "mature" and season == "autumn" and \
                    day - since >= 10:
                plot.update(state="harvested", since=day)
                farmers_took += 1
        if farmers_took:
            self._farmers_harvest(farmers_took, day)

    # ----------------------------------------------------------- player

    def state_at(self, x: int, y: int) -> Optional[str]:
        plot = self.plots.get((x, y))
        return plot["state"] if plot else None

    def harvest(self, x: int, y: int) -> Optional[str]:
        """Z on a mature field tile: the crop is yours."""
        plot = self.plots.get((x, y))
        if not plot or plot["state"] != "mature":
            return None
        from items.item_registry import create_item
        plot.update(state="harvested", since=self._day())
        player = self.engine.player
        got = []
        for _ in range(2):
            item = create_item(CROP_ITEM)
            if item is not None:
                player.inventory.append(item)
                got.append(item.name)
        msg = (f"You harvest the ripe wheat ({len(got)}x "
               f"{got[0]})." if got else "You harvest the field.")
        self.engine.memory_manager.add_event(msg)
        try:
            from engine.skill_progression import add_skill_xp
            for note in add_skill_xp(player, "foraging", 8):
                self.engine.memory_manager.add_event(note)
        except Exception:
            pass
        try:
            from engine.player_deeds import record_deed
            record_deed(self.engine, "harvested the ripe fields")
        except Exception:
            pass
        return msg

    # -------------------------------------------------------- internals

    def _day(self) -> int:
        return self.engine.world.time // (24 * 60)

    def _announce(self, key: str, day: int, note: str) -> None:
        if self._announced.get(key) == day:
            return
        self._announced[key] = day
        self.engine.memory_manager.add_event(f"[Realm] {note}")
        try:
            self.engine.world_director.rumors.append(note)
            del self.engine.world_director.rumors[:-5]
        except Exception:
            pass

    def _farmers_harvest(self, tiles: int, day: int) -> None:
        self._announce("harvest", day,
                       "The farmers have brought the harvest in; "
                       "the granaries fill.")
        try:
            state = self.engine.faction_ticker.state
            state["villagers"]["stores"] = min(
                100, state["villagers"]["stores"] +
                HARVEST_STORES * max(1, tiles // 4))
        except Exception:
            pass

    # ------------------------------------------------------ persistence

    def to_dict(self) -> dict:
        return {"plots": [[list(pos), plot["state"], plot["since"]]
                          for pos, plot in self.plots.items()],
                "announced": dict(self._announced)}

    def from_dict(self, data: dict) -> None:
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        self.plots = {}
        for pos, state, since in data.get("plots", []):
            x, y = int(pos[0]), int(pos[1])
            self.plots[(x, y)] = {"state": state, "since": since}
            try:
                wmap.terrain[y][x] = TerrainType.FARMLAND
            except Exception:
                pass
        self._announced = dict(data.get("announced", {}))
