"""The infection race (P12.12) — RimWorld's three numbers.

A dirty wound can turn: INFECTION grows each night (+28), IMMUNITY
grows each night too (+21, scaled by how you slept — a real bed
x1.5, a camp x1.0, no sleep at all x0.6), and TREATMENT subtracts
(Battle Medicine's graded check, better with a cleric standing at
your shoulder). First to 100 wins:

- immunity 100: the wound knits — you fought it off.
- infection 100: the fever CRISIS — you drop where you stand into
  the P12.4 dying state (the story kills, not the germ), and
  whichever way that resolves the fever breaks back to 60.

Wounds turn dirty where you'd expect: stabilizing in the dirt
(30%), being washed ashore (30%), a crit wound left to bleed (15%).
The hint bar shows the race while it runs. Healers finally matter.
"""

import logging

logger = logging.getLogger("llm_rpg.infection")

INFECTION_PER_NIGHT = 28      # ~0.84/day on RimWorld's scale
IMMUNITY_PER_NIGHT = 21       # ~0.64/day
REST_SCALE = {"bed": 1.5, "camp": 1.0, None: 0.6}
TREAT_CRIT = 35
TREAT_SUCCESS = 20
TREAT_FAIL = 5
CLERIC_ASSIST = 10
CRISIS_RESET = 60


def infected(player) -> bool:
    return player.metadata.get("infection") is not None


def state(player) -> dict:
    return player.metadata.get("infection") or {}


def maybe_infect(engine, chance: float, cause: str = "a dirty wound"
                 ) -> bool:
    """A wound taken in filth may turn. One infection at a time."""
    player = engine.player
    if infected(player):
        return False
    if engine.combat_system.rng.random() >= chance:
        return False
    player.metadata["infection"] = {"progress": 20.0,
                                    "immunity": 0.0,
                                    "cause": cause}
    engine.memory_manager.add_event(
        f"[!] The wound from {cause} is hot and angry — "
        f"it has turned. Treat it, rest well, or race it.")
    return True


def infection_night(engine) -> None:
    """Nightly: the race advances. First to 100 wins."""
    player = engine.player
    quality = player.metadata.pop("slept_quality", None)
    inf = player.metadata.get("infection")
    if inf is None:
        return
    inf["progress"] += INFECTION_PER_NIGHT
    inf["immunity"] += IMMUNITY_PER_NIGHT * REST_SCALE.get(
        quality, 0.6)
    if inf["immunity"] >= 100:
        player.metadata["infection"] = None
        engine.memory_manager.add_event(
            "[!] The wound is cool this morning — your body won "
            "the race. It knits clean.")
        return
    if inf["progress"] >= 100:
        inf["progress"] = CRISIS_RESET
        engine.memory_manager.add_event(
            "[!] The fever CRESTS — the world tilts and goes dark.")
        try:
            from engine.dying import enter_dying, is_dying
            if not is_dying(player):
                enter_dying(engine, player)
        except Exception:
            pass
        return
    engine.memory_manager.add_event(
        f"[!] The infection burns on: {int(inf['progress'])} vs "
        f"your strength {int(inf['immunity'])}. Rest and treatment "
        f"tip the race.")


def treat(engine, result_degree) -> str:
    """Called by Battle Medicine when the patient is infected:
    treatment quality subtracts from the infection."""
    player = engine.player
    inf = player.metadata.get("infection")
    if inf is None:
        return ""
    from engine.skills import Degree
    amount = {Degree.CRIT_SUCCESS: TREAT_CRIT,
              Degree.SUCCESS: TREAT_SUCCESS}.get(result_degree,
                                                 TREAT_FAIL)
    assist = ""
    if _cleric_near(engine):
        amount += CLERIC_ASSIST
        assist = " The priest's steady hands guide yours."
    inf["progress"] = max(0.0, inf["progress"] - amount)
    if inf["progress"] <= 0:
        player.metadata["infection"] = None
        return (f" The wound drains clean — the infection is "
                f"beaten.{assist}")
    return (f" You clean the infected wound (-{amount}, now "
            f"{int(inf['progress'])}).{assist}")


def hint(engine) -> str:
    inf = engine.player.metadata.get("infection")
    if inf is None:
        return ""
    return (f"[!] infection {int(inf['progress'])} vs immunity "
            f"{int(inf['immunity'])} — treat (SHIFT+H) and sleep "
            f"well")


def _cleric_near(engine) -> bool:
    try:
        from engine.presence import npc_adjacent_to_player
        return any(
            npc_adjacent_to_player(engine, n, 1.5)
            for n in engine.npc_manager.npcs.values()
            if n.is_active() and
            getattr(n.character_class, "value", "") in
            ("cleric", "paladin"))
    except Exception:
        return False
