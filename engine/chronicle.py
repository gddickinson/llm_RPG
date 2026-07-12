"""Runtime history — the saga accrues (P20.5).

The world's history was written once, before the game began: an eight-event
pre-game sim, fixed in `world_history`, that never grew. Everything that
happened AFTER — a nemesis finally slain, two factions going to war, a
god's wrath, a castle besieged — vanished into a five-slot rumor pool. The
world had a past but no memory of the present.

This keeps a CHRONICLE that grows as you play. Registered as an observer on
the event log, it watches for the beats that shape an age — anything the
game already marks `[Legend]` (a nemesis's fall, a lair cleared, a true
death), plus the weightiest `[Realm]` beats (wars and alliances, a god
contending, a tribe swarming out or beaten back, a siege) — and writes each
into a dated saga you can read in the Y-journal, under the pre-game legends.
So the realm remembers what you did to it.

Deterministic; the chronicle persists.
"""

import logging

logger = logging.getLogger("llm_rpg.chronicle")

MAX_ENTRIES = 60
SHOWN = 20

# Beats that shape an age. `[Legend]` is already the game's curated
# "this is weighty" prefix; these keywords catch the faction/divine/tribe
# beats that ride the busier `[Realm]` prefix.
SAGA_KEYWORDS = (
    "are at war", "sworn an alliance", "have allied",
    "falls at last", "the grudge ends", "returns to hunt",
    "move to dominate", "beaten low", "have recovered",
    "gods contend", "swarm out", "beaten back",
    "the castle falls", "lay siege", "besiege", "is slain",
)


class Chronicle:
    def __init__(self, engine):
        self.engine = engine
        self.entries: list = []          # [{day, text}, ...]

    # ---- capture ---------------------------------------------------

    def _worthy(self, text: str) -> bool:
        if text.startswith("[Legend]"):
            return True
        low = text.lower()
        return any(k in low for k in SAGA_KEYWORDS)

    def record(self, event) -> None:
        """A memory-manager observer — capture saga-worthy beats."""
        text = event if isinstance(event, str) else str(event)
        if not text or not self._worthy(text):
            return
        clean = text.split("] ", 1)[-1] if text.startswith("[") else text
        clean = clean.strip()
        if not clean:
            return
        if self.entries and self.entries[-1]["text"] == clean:
            return                       # no consecutive repeats
        day = self.engine.world.time // (24 * 60)
        self.entries.append({"day": day, "text": clean})
        del self.entries[:-MAX_ENTRIES]

    # ---- the journal view ------------------------------------------

    def lines(self) -> list:
        if not self.entries:
            return []
        out = ["", "Chronicle of the Age",
               "(the saga of your own deeds and the realm's)", ""]
        for e in self.entries[-SHOWN:]:
            out.append(f"* Day {e['day']}: {e['text']}")
        return out

    def tail(self, k: int = 5) -> list:
        return self.entries[-k:]

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"entries": self.entries}

    def from_dict(self, d: dict) -> None:
        self.entries = (d or {}).get("entries", []) or []
