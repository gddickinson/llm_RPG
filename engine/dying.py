"""Dying & Wounded (P12.4) — the space between 0 HP and the story.

PLAYER: dropping to 0 no longer resolves instantly. You go DOWN:
Dying N (starting at 1 + your Wounded count) with a flat recovery
check each turn — DC 10: succeed and Dying falls 1, fail and it
rises 1, nat 20/1 move it 2. Reach 0 and you STABILIZE: Wounded
climbs by one (each knockdown brings the next closer) and the
failure-as-story outcome fires in its gentle form (robbed or left
for dead — you were helpless either way). Reach Dying 4 and the
FULL defeat table resolves, slain included. Taking a hit while
down worsens Dying by 1. A real night's sleep clears Wounded.

NPCS (the Kenshi lesson): people are KNOCKED OUT, monsters die.
A person beaten to 0 drops unconscious for hours — a body you can
ROB (E on the body takes their purse and they remember it), that
wakes on its own in the overnight stack with a grudge. Ransom and
rescue beats are the noted remainder.
"""

import logging
import random
from typing import Optional

logger = logging.getLogger("llm_rpg.dying")

DYING_MAX = 4
RECOVERY_DC = 10
KO_HOURS = 6
PERSON_CLASSES = ("guard", "paladin", "villager", "merchant",
                  "bard", "cleric", "brigand", "wizard", "ranger")


def is_dying(player) -> bool:
    return player.metadata.get("dying", 0) > 0


def wounded(player) -> int:
    return int(player.metadata.get("wounded", 0))


def enter_dying(engine, attacker) -> str:
    """0 HP: go down instead of resolving. Wounded feeds the start."""
    player = engine.player
    player.hp = 1                     # alive-checks stay harmless
    start = min(DYING_MAX, 1 + wounded(player))
    player.metadata["dying"] = start
    player.metadata["dying_attacker"] = getattr(attacker, "name",
                                                "your wounds")
    msg = (f"[!] You collapse — DYING {start}/{DYING_MAX}! "
           f"Fight for every breath...")
    engine.memory_manager.add_event(msg)
    if start >= DYING_MAX:
        return _final(engine, attacker)
    return msg


def worsen(engine, attacker) -> str:
    """A hit while down drives the wound deeper."""
    player = engine.player
    player.hp = 1
    player.metadata["dying"] = player.metadata.get("dying", 1) + 1
    d = player.metadata["dying"]
    if d >= DYING_MAX:
        return _final(engine, attacker)
    msg = f"[!] The blow drives you deeper — DYING {d}/{DYING_MAX}!"
    engine.memory_manager.add_event(msg)
    return msg


def dying_tick(engine, rng: random.Random = None) -> None:
    """One recovery check per turn while down (flat DC 10)."""
    player = engine.player
    d = player.metadata.get("dying", 0)
    if d <= 0:
        return
    rng = rng or engine.combat_system.rng
    d20 = rng.randint(1, 20)
    if d20 == 20:
        d -= 2
    elif d20 >= RECOVERY_DC:
        d -= 1
    elif d20 == 1:
        d += 2
    else:
        d += 1
    if d <= 0:
        _stabilize(engine)
        return
    player.metadata["dying"] = d
    if d >= DYING_MAX:
        _final(engine, None)
        return
    engine.memory_manager.add_event(
        f"[!] DYING {d}/{DYING_MAX} — "
        f"{'the bleeding slows' if d20 >= RECOVERY_DC else 'you slip further'}...")


def action_gate(engine) -> Optional[str]:
    """Downed players don't act; trying costs the turn."""
    if not is_dying(engine.player):
        return None
    return ("You are down, fighting for your life — "
            "the world moves without you.")


def _stabilize(engine) -> None:
    """Dying 0: you live — helpless, so the gentle beats resolve."""
    player = engine.player
    player.metadata["dying"] = 0
    player.metadata["wounded"] = wounded(player) + 1
    engine.memory_manager.add_event(
        f"[!] You stabilize... (Wounded {wounded(player)} — the next "
        f"fall comes faster. Sleep it off.)")
    from engine.defeat import _left_for_dead, _robbed
    rng = engine.combat_system.rng
    if rng.random() < 0.5:
        _robbed(engine, None, rng)
    else:
        _left_for_dead(engine)


def _final(engine, attacker) -> str:
    """Dying 4: the full defeat table, slain included."""
    player = engine.player
    player.metadata["dying"] = 0
    player.metadata["wounded"] = wounded(player) + 1
    from engine.defeat import handle_player_defeat
    survived, msg = handle_player_defeat(
        engine, attacker or player, rng=engine.combat_system.rng)
    engine.memory_manager.add_event(msg)
    if not survived:
        player.defeat()
        engine.player_dead = True
        if not getattr(engine, "_has_gui", False):
            engine.end_game()
    return msg


# ------------------------------------------------ NPC soft-states

def is_person(npc) -> bool:
    return getattr(getattr(npc, "character_class", None),
                   "value", "") in PERSON_CLASSES


def ko_person(engine, attacker, npc) -> str:
    """People drop unconscious — a body to rob, not a corpse."""
    npc.defeat()
    npc.last_position = npc.position
    npc.metadata["ko_until"] = engine.world.time + KO_HOURS * 60
    npc.metadata["ko_by"] = getattr(attacker, "name", "someone")
    engine.world.add_item_to_ground(
        f"{npc.name}'s body", npc.position[0], npc.position[1])
    engine.world.map.remove_character(npc)
    msg = (f"{attacker.name} beats {npc.name} senseless — they crumple "
           f"where they stand.")
    engine.memory_manager.add_event(msg)
    return msg


def rob_body(engine, marker: str, x: int, y: int) -> Optional[str]:
    """E on a KO'd person's body: take their purse. They'll know."""
    name = marker[:-7] if marker.endswith("'s body") else marker
    npc = next((n for n in engine.npc_manager.npcs.values()
                if n.name == name and not n.is_active()
                and n.metadata.get("ko_until")), None)
    if npc is None or npc.gold <= 0:
        return None
    taken = npc.gold
    npc.gold = 0
    engine.player.gold += taken
    npc.modify_relationship(engine.player.id, -30)
    try:
        from engine.npc_memory import remember
        remember(npc, f"{engine.player.name} robbed me of {taken}g "
                      f"while I lay senseless.", 8, engine.world.time)
    except Exception:
        pass
    msg = f"You go through {name}'s pockets: {taken}g. They'll remember."
    engine.memory_manager.add_event(msg)
    return msg


def wake_the_fallen(engine) -> int:
    """Overnight: the beaten come to, nursing grudges."""
    woke = 0
    for npc in engine.npc_manager.npcs.values():
        until = npc.metadata.get("ko_until")
        if until is None or npc.is_active() or \
                engine.world.time < until:
            continue
        npc.metadata.pop("ko_until", None)
        npc.status = "alive"
        npc.hp = max(1, npc.max_hp // 3)
        pos = getattr(npc, "last_position", npc.position)
        if engine.world.map.get_character_at(*pos) is None:
            npc.position = pos
            engine.world.map.place_character(npc, *pos)
        try:
            engine.world.remove_item_from_ground(
                f"{npc.name}'s body", *pos)
        except Exception:
            pass
        try:
            from engine.npc_memory import remember
            remember(npc, f"{npc.metadata.get('ko_by', 'Someone')} "
                          f"beat me unconscious.", 7,
                     engine.world.time)
        except Exception:
            pass
        engine.memory_manager.add_event(
            f"[Overnight] {npc.name} comes to, aching and angry.")
        woke += 1
    return woke
