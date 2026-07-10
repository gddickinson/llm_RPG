"""Disease & contagion (P8.2, pattern ported from autonomous_world).

Sickness is a world event, not a stat sheet: outbreaks start with a
patient zero on season-biased odds, spread between people standing
near each other (never monsters), run their course in days, and leave
immunity behind. The player can catch anything — a daily symptom drain
that weakens but never kills (floored at 1 HP, like hunger) — and the
right remedy from `data/diseases.json` cures it (drunk via the normal
item-use flow). Events use the `[Realm]` prefix so outbreaks enter the
rumor mill and the topic journal like any other news.

All infection state rides `character.metadata` ("disease",
"disease_immunity"), so saves work for free. One check per game night,
zero LLM. Content is data: add a disease by editing the JSON.
"""

import json
import logging
import os
import random
from typing import Dict, Optional

logger = logging.getLogger("llm_rpg.disease")

OUTBREAK_CHANCE = 0.08          # per matching disease, per quiet night
SPREAD_RADIUS = 3               # tiles
SUSCEPTIBLE = ("villager", "merchant", "guard", "bard", "cleric",
               "paladin", "brigand")


def _load() -> Dict[str, dict]:
    try:
        with open(os.path.join("data", "diseases.json")) as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("diseases.json missing/corrupt; diseases off")
        return {}


DISEASES: Dict[str, dict] = _load()


def is_infected(char) -> bool:
    return bool(getattr(char, "metadata", {}).get("disease"))


def try_cure_with_item(engine, char, item) -> Optional[str]:
    """The right remedy clears the sickness. Returns the message."""
    state = getattr(char, "metadata", {}).get("disease")
    if not state:
        return None
    spec = DISEASES.get(state.get("id"), {})
    if getattr(item, "id", "") != spec.get("cure_item"):
        return None
    engine.disease.cure(char)
    msg = (f"You drink the {item.name} and feel the "
           f"{spec.get('name', 'sickness')} lift.")
    engine.memory_manager.add_event(msg)
    return msg


class DiseaseSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    # ------------------------------------------------------------ api

    def infect(self, char, disease_id: str, quiet: bool = False) -> bool:
        spec = DISEASES.get(disease_id)
        if spec is None or is_infected(char):
            return False
        meta = char.metadata
        immunity = meta.get("disease_immunity", {})
        if immunity.get(disease_id, -1) >= self._day():
            return False
        meta["disease"] = {"id": disease_id, "caught": self._day()}
        if not quiet and char.id == self.engine.player.id:
            self.engine.memory_manager.add_event(
                f"You have caught {spec['name']} — {spec['symptom']} "
                f"takes hold. ({spec['cure_item']} cures it.)")
        return True

    def cure(self, char) -> None:
        char.metadata.pop("disease", None)

    # -------------------------------------------------------- nightly

    def run_day(self) -> int:
        """Progress, spread, and maybe start sickness. Returns number
        of new infections."""
        if not DISEASES:
            return 0
        engine, day = self.engine, self._day()
        people = self._people()
        infected = [c for c in people if is_infected(c)]
        for char in infected:
            self._progress(char, day)
        infected = [c for c in people if is_infected(c)]
        new = 0
        for char in infected:
            new += self._spread(char, people)
        if not infected:
            new += self._maybe_outbreak(people)
        self._player_symptoms()
        return new

    # ------------------------------------------------------- internals

    def _day(self) -> int:
        return self.engine.world.time // (24 * 60)

    def _people(self):
        """Everyone who can sicken. Progression applies to all of
        them; _spread additionally requires standing on the overworld
        grid (zone NPCs' coordinates live in another space)."""
        engine = self.engine
        out = [n for n in engine.npc_manager.npcs.values()
               if n.is_active()
               and getattr(n.character_class, "value", "")
               in SUSCEPTIBLE]
        out.append(engine.player)
        return out

    def _progress(self, char, day: int) -> None:
        state = char.metadata["disease"]
        spec = DISEASES.get(state["id"])
        if spec is None:
            self.cure(char)
            return
        if day - state.get("caught", day) >= spec["duration_days"]:
            self.cure(char)
            char.metadata.setdefault("disease_immunity", {})[
                state["id"]] = day + spec.get("immunity_days", 20)
            if char.id == self.engine.player.id:
                self.engine.memory_manager.add_event(
                    f"Your {spec['name']} has run its course. "
                    f"You feel yourself again.")

    def _spread(self, carrier, people) -> int:
        state = carrier.metadata.get("disease")
        spec = DISEASES.get(state["id"]) if state else None
        if spec is None:
            return 0
        wmap = self.engine.world.map
        if wmap.get_character_at(*carrier.position) is not carrier \
                and carrier.id != self.engine.player.id:
            return 0
        cx, cy = carrier.position
        new = 0
        for other in people:
            if other.id == carrier.id or is_infected(other):
                continue
            if other.id != self.engine.player.id and \
                    wmap.get_character_at(*other.position) is not other:
                continue
            ox, oy = other.position
            if abs(ox - cx) + abs(oy - cy) > SPREAD_RADIUS:
                continue
            if self.rng.random() < spec["spread_chance"]:
                if self.infect(other, state["id"]):
                    new += 1
        return new

    def _maybe_outbreak(self, people) -> int:
        try:
            season = self.engine.world.get_date().season.value
        except Exception:
            season = "any"
        candidates = [c for c in people
                      if c.id != self.engine.player.id]
        if not candidates:
            return 0
        for did, spec in DISEASES.items():
            if spec.get("season", "any") not in ("any", season):
                continue
            if self.rng.random() >= OUTBREAK_CHANCE:
                continue
            zero = self.rng.choice(candidates)
            if self.infect(zero, did, quiet=True):
                note = (f"{spec['symptom'].capitalize()} is going "
                        f"around — folk whisper of {spec['name']}.")
                self.engine.memory_manager.add_event(f"[Realm] {note}")
                try:
                    self.engine.world_director.rumors.append(note)
                    del self.engine.world_director.rumors[:-5]
                except Exception:
                    pass
                return 1
        return 0

    def _player_symptoms(self) -> None:
        player = self.engine.player
        state = getattr(player, "metadata", {}).get("disease")
        if not state:
            return
        spec = DISEASES.get(state["id"])
        if spec is None:
            return
        drain = int(spec.get("severity", 1))
        if player.hp > 1:
            player.hp = max(1, player.hp - drain)
        self.engine.memory_manager.add_event(
            f"{spec['name']} weakens you — {spec['symptom']} "
            f"(-{drain} HP).")
