"""Player tactical verbs (P5.3): opportunity attacks, disengage, shove.

SHIFT is the tactical modifier:
- SHIFT+move  — disengage: retreat carefully, immune to opportunity
                attacks, but the care costs an extra minute.
- SHIFT+F     — shove: STR contest; push the adjacent enemy back one
                tile and open space to flee or shoot.
- SHIFT+R     — aimed shot: +2 damage, +1 minute (in game_api_mixin).

Plain movement away from an adjacent hostile now provokes a free strike
— retreat is a decision, not a freebie.
"""

import logging
import random
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.tactics")

DISENGAGE_EXTRA_MINUTES = 1


def adjacent_hostiles(engine, pos: Tuple[int, int]) -> List:
    out = []
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        klass = getattr(npc.character_class, "value", "")
        if klass not in ("brigand", "monster", "troll"):
            continue
        d = max(abs(npc.position[0] - pos[0]),
                abs(npc.position[1] - pos[1]))
        if d <= 1:
            out.append(npc)
    return out


def opportunity_attack(engine, old_pos: Tuple[int, int]) -> Optional[str]:
    """After the player moves: hostiles adjacent to the OLD position
    that are no longer adjacent get one free strike (the nearest one)."""
    new_pos = engine.player.position
    leavers = [h for h in adjacent_hostiles(engine, old_pos)
               if max(abs(h.position[0] - new_pos[0]),
                      abs(h.position[1] - new_pos[1])) > 1]
    if not leavers:
        return None
    striker = leavers[0]
    engine.memory_manager.add_event(
        f"{striker.name} lashes out as you turn to flee!")
    try:
        return engine.combat_system._resolve(striker, engine.player)
    except Exception as e:
        logger.debug(f"opportunity strike failed: {e}")
        return None


def disengage_cost(engine) -> None:
    engine.world.advance_time(DISENGAGE_EXTRA_MINUTES)


def shove(engine, rng: random.Random = None) -> str:
    """STR contest vs the nearest adjacent hostile; push them one tile
    directly away. Blocked tiles make the shove fail."""
    rng = rng or random.Random()
    player = engine.player
    hostiles = adjacent_hostiles(engine, player.position)
    if not hostiles:
        return "No enemy close enough to shove."
    target = hostiles[0]

    try:                                        # P34.21 a shove is exertion
        from engine import stamina
        mine_ex = stamina.exertion_penalty(player)
        stamina.spend_action(player)
    except Exception:
        mine_ex = 0
    mine = rng.randint(1, 20) + player.get_stat_modifier("strength") - mine_ex
    theirs = rng.randint(1, 20) + target.get_stat_modifier("strength")
    margin = mine - theirs                      # P12.1 degrees
    if margin <= 0:
        msg = f"You shove {target.name}, but they hold their ground!"
        if margin <= -10:
            # critical loss: the counter-shove staggers YOU
            px, py = player.position
            back = (px - (target.position[0] - px),
                    py - (target.position[1] - py))
            wmap = engine.world.map
            if wmap.move_character(player, *back):
                msg = (f"{target.name} counter-shoves you — you "
                       f"stagger backward!")
        engine.memory_manager.add_event(msg)
        engine.advance_turn()
        return msg

    dx = target.position[0] - player.position[0]
    dy = target.position[1] - player.position[1]
    step = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    nx, ny = target.position[0] + step[0], target.position[1] + step[1]
    wmap = engine.world.map
    from world.world_map import TerrainType
    pushable = (0 <= nx < wmap.width and 0 <= ny < wmap.height and
                wmap.get_terrain_at(nx, ny) not in
                (TerrainType.WATER, TerrainType.MOUNTAIN,
                 TerrainType.BUILDING) and
                not any(n.is_active() and n.position == (nx, ny)
                        for n in engine.npc_manager.npcs.values()))
    if pushable:
        wmap.remove_character(target)
        target.position = (nx, ny)
        wmap.place_character(target, nx, ny)
        # staggered: it doesn't get to step back at you this same turn
        # (P32.1 pursuit skips a freshly-shoved creature once)
        target.metadata["shoved"] = True
        try:                                        # P34.19 knocked-back tumble
            from engine import anim
            anim.launch(target, player.position)
        except Exception:
            pass
        msg = f"You slam into {target.name} and send them staggering back!"
        if margin >= 10:                        # critical: a second tile
            fx, fy = nx + step[0], ny + step[1]
            if (0 <= fx < wmap.width and 0 <= fy < wmap.height and
                    wmap.get_terrain_at(fx, fy) not in
                    (TerrainType.WATER, TerrainType.MOUNTAIN,
                     TerrainType.BUILDING) and
                    not any(n.is_active() and n.position == (fx, fy)
                            for n in engine.npc_manager.npcs.values())):
                wmap.remove_character(target)
                target.position = (fx, fy)
                wmap.place_character(target, fx, fy)
                msg = (f"You hurl {target.name} sprawling — they "
                       f"tumble two full paces back!")
                from characters.status_effects import apply_effect
                apply_effect(target, "prone", duration=3)
                from engine import anim         # they go down and get back up
                anim.interact(player, target, "knockdown")
    else:
        msg = (f"You shove {target.name} against the "
               f"obstruction — they stumble but hold.")
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg


# --------------------------------------------------------------- grapple & throw
# I3 (George: "wrestling, throwing each other, more contact when fighting").
# SHIFT+C clinches an adjacent foe (a STR contest — both play the wrestle clip);
# press it again while clinched to THROW the foe (an amplified shove + a hard
# knockdown).  A grabbed foe is left OFF-GUARD (easier to hit) so the grapple
# pays off even if you don't follow through.

def _contest(player, target, rng, mine_bonus=0):
    """A STR-vs-(STR|DEX) opposed check; returns the player's margin (P12.1)."""
    try:
        from engine import stamina
        mine_ex = stamina.exertion_penalty(player)
        stamina.spend_action(player)
    except Exception:
        mine_ex = 0
    mine = (rng.randint(1, 20) + player.get_stat_modifier("strength")
            + mine_bonus - mine_ex)
    resist = max(target.get_stat_modifier("strength"),
                 target.get_stat_modifier("dexterity"))
    return mine - (rng.randint(1, 20) + resist)


def is_grappling(engine) -> bool:
    """True when the player holds a still-adjacent, still-living foe in a clinch."""
    gid = (engine.player.metadata or {}).get("grappling")
    if not gid:
        return False
    px, py = engine.player.position
    for n in engine.npc_manager.npcs.values():
        if n.id == gid and n.is_active():
            return max(abs(n.position[0] - px), abs(n.position[1] - py)) <= 1
    return False


def grapple(engine, rng: random.Random = None) -> str:
    """Clinch the nearest adjacent hostile (a STR contest). Win → the foe is
    GRABBED (off-guard; a firm win pins it PRONE) and the player holds the
    clinch; a bad loss throws the player off balance."""
    rng = rng or random.Random()
    player = engine.player
    hostiles = adjacent_hostiles(engine, player.position)
    if not hostiles:
        return "No enemy close enough to grapple."
    target = hostiles[0]
    from engine import anim
    anim.interact(player, target, "wrestle")            # both grapple
    from characters.status_effects import apply_effect
    margin = _contest(player, target, rng)
    if margin <= 0:
        msg = f"You lunge for {target.name}, but they break your grip!"
        if margin <= -10:
            apply_effect(player, "off_guard", duration=2)
            msg = f"{target.name} twists free and throws YOU off balance!"
        engine.memory_manager.add_event(msg)
        engine.advance_turn()
        return msg
    apply_effect(target, "off_guard", duration=3)
    player.metadata["grappling"] = target.id
    target.metadata["grappled_by"] = player.id
    msg = f"You seize {target.name} in a grapple — they're off balance!"
    if margin >= 10:
        apply_effect(target, "prone", duration=2)
        msg = f"You wrench {target.name} down and pin them, reeling!"
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg


def throw(engine, rng: random.Random = None) -> str:
    """Hurl a grappled (or, failing that, the nearest adjacent) foe through the
    air — an amplified shove (up to 2 tiles) + a hard KNOCKDOWN + fall damage.
    A grabbed foe is far easier to throw than a loose one."""
    rng = rng or random.Random()
    player = engine.player
    gid = (player.metadata or {}).get("grappling")
    target = None
    if gid:
        target = next((n for n in engine.npc_manager.npcs.values()
                       if n.id == gid and n.is_active()), None)
    if target is None:
        hostiles = adjacent_hostiles(engine, player.position)
        target = hostiles[0] if hostiles else None
    if target is None:
        return "No one in your grip to throw."
    grabbed = (target.metadata or {}).get("grappled_by") == player.id
    player.metadata.pop("grappling", None)
    target.metadata.pop("grappled_by", None)
    if _contest(player, target, rng, mine_bonus=4 if grabbed else 0) <= 0:
        msg = f"You heave at {target.name}, but can't get the leverage!"
        engine.memory_manager.add_event(msg)
        engine.advance_turn()
        return msg
    from engine import anim
    from characters.status_effects import apply_effect
    from world.world_map import TerrainType
    anim.interact(player, target, "throw")              # a hurls, b tumbles
    dx = target.position[0] - player.position[0]
    dy = target.position[1] - player.position[1]
    step = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    if step == (0, 0):
        step = (1, 0)
    wmap = engine.world.map
    landed = target.position
    for _ in range(2):                                  # sail up to two tiles
        nx, ny = landed[0] + step[0], landed[1] + step[1]
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            break
        if wmap.get_terrain_at(nx, ny) in (
                TerrainType.WATER, TerrainType.MOUNTAIN, TerrainType.BUILDING):
            break
        if any(n.is_active() and n.position == (nx, ny)
               for n in engine.npc_manager.npcs.values()):
            break
        landed = (nx, ny)
    if landed != target.position:
        wmap.remove_character(target)
        target.position = landed
        wmap.place_character(target, *landed)
        target.metadata["shoved"] = True                # skips its next pursuit
    apply_effect(target, "prone", duration=3)
    dmg = max(1, 2 + player.get_stat_modifier("strength"))
    target.take_damage(dmg)
    try:
        anim.launch(target, player.position)            # a tumbling arc (P34.19)
    except Exception:
        pass
    msg = (f"You hurl {target.name} through the air — "
           f"they crash down hard! (-{dmg} HP)")
    if not target.is_alive():
        try:
            engine.combat_system._handle_defeat(player, target, dmg)
        except Exception:
            pass
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg
