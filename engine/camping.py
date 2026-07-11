"""Camping + the DM's night (P12.6) — rest with teeth.

CAMP: press Enter anywhere outdoors and you make camp. A real camp
CONSUMES PROVISIONS (BG3): food from your pack worth SUPPLY_NEED
in heal-value goes into the fire and your belly. Supplied, you
sleep to dawn — half heal, fatigue and sleep debt cleared, a real
night. Undersupplied you only DOZE: some tiredness fades, but the
debt stays and the night is wasted. The wilderness can INTERRUPT:
a roll each camp wakes you to something prowling the firelight —
reduced recovery and a fight for breakfast.

THE DM'S NIGHT: every sleep — inn or camp — ends with the DM's
guaranteed beat: a `[DM]` dream stitched from the living world
(rumors, your deeds, the gods) that the AutonomousDM can override
with an authored scene when an LLM is at the table.

Inn tiers (Skyrim): a private room (15g) grants WELL_RESTED —
+10% XP until the next night — while the 5g bunk just sleeps you.
"""

import logging
from typing import List, Optional

logger = logging.getLogger("llm_rpg.camping")

SUPPLY_NEED = 8            # heal-value of food a real camp burns
CAMP_HEAL_FRACTION = 0.50
AMBUSH_HEAL_FRACTION = 0.25
AMBUSH_CHANCE = 0.25
WATCHED_AMBUSH_CHANCE = 0.10   # a companion on watch (P15.5)
DOZE_FATIGUE_RELIEF = 40
STOCK_DREAMS = (
    "You dream of a door in the mountainside that was never there.",
    "You dream of rain falling upward into a violet sky.",
    "You dream of a table set for guests who never arrive.",
    "You dream of bells beneath the water, ringing for you.",
)


def can_camp(engine) -> Optional[str]:
    try:
        if engine.active_zone() is not None:
            return "You can't pitch camp indoors."
    except Exception:
        pass
    return None


def _gather_supplies(player) -> int:
    """Burn food worth SUPPLY_NEED from the pack. Returns value
    consumed (may fall short)."""
    value = 0
    for item in list(player.inventory):
        if value >= SUPPLY_NEED:
            break
        eff = getattr(item, "use_effect", None) or {}
        heal = getattr(item, "heal_amount", 0)
        if not eff.get("food") or heal <= 0:
            continue
        value += heal
        if getattr(item, "stackable", False) and item.quantity > 1:
            item.quantity -= 1
        else:
            player.inventory.remove(item)
    return value


def camp(engine) -> List[str]:
    """Sleep under the stars. Returns day-summary overlay lines."""
    reason = can_camp(engine)
    if reason:
        engine.memory_manager.add_event(reason)
        return []
    player = engine.player
    supplies = _gather_supplies(player)
    now = engine.world.time
    day = now // (24 * 60)

    if supplies < SUPPLY_NEED:
        # a hungry doze — tiredness fades, the debt does not
        engine.world.advance_time(6 * 60)
        meta = player.metadata
        meta["fatigue"] = max(0, meta.get("fatigue", 0)
                              - DOZE_FATIGUE_RELIEF)
        engine.advance_turn()
        msg = ("Without provisions you doze fitfully by a cold "
               "fire — poor rest, and the night is wasted.")
        engine.memory_manager.add_event(msg)
        return [msg, "",
                "(A real camp burns food from your pack — "
                "carry provisions.)"]

    player.metadata["slept_day"] = day
    player.metadata["slept_quality"] = "camp"    # P12.12
    from engine.rest import WAKE_HOUR, snapshot
    before = getattr(engine, "_day_metrics", None) or snapshot(engine)
    minutes_per_day = 24 * 60
    wake = (day + 1) * minutes_per_day + WAKE_HOUR * 60
    engine.world.advance_time(wake - now)
    engine.advance_turn()                 # the nightly stack fires

    rng = engine.combat_system.rng
    watcher = next((n for n in engine.companion_manager.members()
                    if n.is_active()), None)
    chance = WATCHED_AMBUSH_CHANCE if watcher else AMBUSH_CHANCE
    ambushed = rng.random() < chance
    heal_frac = AMBUSH_HEAL_FRACTION if ambushed else \
        CAMP_HEAL_FRACTION
    player.hp = min(player.max_hp,
                    player.hp + int(player.max_hp * heal_frac))
    player.metadata["fatigue"] = 0
    player.metadata["sleep_debt"] = 0
    player.metadata["wounded"] = 0
    player.metadata["weapon_action_used"] = False   # P12.7
    player.metadata["hunger"] = min(
        player.metadata.get("hunger", 20), 30)

    lines = [f"You camp under the open sky. (supplies: {supplies} "
             f"worth of provisions burned)"]
    if watcher is not None:
        lines.append(f"{watcher.name} takes the first watch, "
                     f"firelight on their face.")
    if ambushed:
        lines.append(_spring_ambush(engine))
    else:
        engine.memory_manager.add_event(
            "You sleep rough but sound, and wake with the sun.")
    lines.append("")
    lines.append(night_beat(engine))
    engine._day_metrics = snapshot(engine)
    return lines


def _spring_ambush(engine) -> str:
    """Something found the fire. It waits for you at dawn."""
    player = engine.player
    px, py = player.position
    wmap = engine.world.map
    from world.monsters import build_monster
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = px + dx, py + dy
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            continue
        if wmap.get_character_at(nx, ny) is not None:
            continue
        from world.world_map import TerrainType
        if wmap.terrain[ny][nx] in (TerrainType.WATER,
                                    TerrainType.MOUNTAIN,
                                    TerrainType.BUILDING):
            continue
        beast = build_monster("wolf", (nx, ny))
        engine.npc_manager.add_npc(beast)
        wmap.place_character(beast, nx, ny)
        break
    msg = ("[!] You wake with a start — something prowled the "
           "camp in the night, and it hasn't left!")
    engine.memory_manager.add_event(msg)
    return msg


def night_beat(engine) -> str:
    """The DM's guaranteed slot: every night, the world speaks."""
    rng = engine.combat_system.rng
    dream = None
    try:   # the AutonomousDM may have an authored scene queued
        note = getattr(engine.dm_autonomous, "night_scene", None)
        if note:
            dream = note
            engine.dm_autonomous.night_scene = None
    except Exception:
        pass
    if dream is None:
        try:
            from engine.player_deeds import recent_deeds
            deeds = recent_deeds(engine, k=3)
            rumors = list(getattr(engine.world_director, "rumors",
                                  []))
            pool = []
            if deeds:
                pool.append("You dream again of the moment you "
                            f"{deeds[-1]}.")
            if rumors:
                pool.append("Voices whisper through your sleep: "
                            f"'{rumors[-1]}'")
            pool.extend(STOCK_DREAMS)
            dream = pool[rng.randint(0, len(pool) - 1)] \
                if hasattr(rng, "randint") else pool[0]
        except Exception:
            dream = STOCK_DREAMS[0]
    msg = f"[DM] {dream}"
    engine.memory_manager.add_event(msg)
    return msg
