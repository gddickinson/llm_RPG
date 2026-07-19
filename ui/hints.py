"""Contextual key hints — the game's ambient tutorial.

`context_hints(engine)` inspects what's around the player and returns
up to MAX_HINTS prioritized one-liners like "[B] barter with Durgan".
Pure logic (no pygame) so it's unit-testable; the HUD renders the strings.
"""

import logging
from typing import List

logger = logging.getLogger("llm_rpg.hints")

MAX_HINTS = 3
COMBAT_HINTS = 6        # T3.3 a fight is dense with verbs (trip/feint/grapple/…) —
#                         show more when a foe is adjacent so they aren't starved


def _adjacent_npcs(engine, radius: float = 1.5):
    from engine.presence import npc_adjacent_to_player
    return [npc for npc in engine.npc_manager.npcs.values()
            if npc.is_active()
            and npc_adjacent_to_player(engine, npc, radius)]


def _hostile(npc) -> bool:
    return getattr(npc.character_class, "value", "") in (
        "brigand", "troll", "monster")


def context_hints(engine) -> List[str]:
    """Ordered, deduplicated key hints for the player's surroundings."""
    hints: List[str] = []
    player = engine.player
    x, y = player.position

    # The law outranks everything but dying (P12.9)
    try:
        if getattr(engine.law, "active", None):
            a = engine.law.active
            return [f"[Law] 1 pay {a['amount']}g · 2 jail · "
                    f"3 bribe · 4 talk · 5 resist"]
    except Exception:
        pass

    # Dying dominates every other hint (P12.4)
    try:
        from engine.dying import DYING_MAX
        d = player.metadata.get("dying", 0)
        if d > 0:
            return [f"[!] DYING {d}/{DYING_MAX} — fight for it!"]
    except Exception:
        pass

    # The combat-testing colosseum — stage a fight at the arena gate
    try:
        col = getattr(engine, "colosseum", None)
        if col is not None and not engine.current_interior \
                and col.at_entrance((x, y)):
            hints.append("[Arena] the bout rages — [E] a new matchup"
                         if col.active else "[E] stage a colosseum matchup")
    except Exception:
        pass

    # Unclaimed bloodstain — your loot is out there (soulslike)
    try:
        from engine.checkpoint import bloodstain_pos
        bp = bloodstain_pos(engine)
        if bp is not None:
            hints.append(f"[!] Your remains lie at ({bp[0]}, {bp[1]}) "
                         f"— return to reclaim your pack")
    except Exception:
        pass

    # Tutorial lessons lead everything
    try:
        from engine.tutorial import hint_lines
        hints.extend(hint_lines(engine))
    except Exception:
        pass

    # GAP.2 a freshly-unlocked Field Guide entry — nudge them to read it (Y)
    try:
        n = engine.codex.unseen()
        if n > 0:
            hints.append(f"[Y] journal — {n} new entr"
                         + ("ies" if n > 1 else "y"))
    except Exception:
        pass

    # GAP.3 crawling = sneaking: advertise the sneak-attack payoff
    try:
        from engine import stealth
        if stealth.is_sneaking(player):
            hints.append("Sneaking — a strike on an unaware foe is a "
                         "SNEAK ATTACK")
    except Exception:
        pass

    # GX.5 the Deepdelve — its cues lead: finding the secret stair (the sole
    # discovery mechanism) and descending a mouth must NOT be crowded out of
    # the capped hint bar by ambient talk/barter prompts when it sits in town.
    if not getattr(engine, "current_interior", None) and \
            not getattr(engine, "current_dungeon", None):
        try:
            from world.world_map import TerrainType
            x, y = engine.player.position
            dd = getattr(engine, "deepdelve", None)
            if engine.world.map.get_terrain_at(x, y) == TerrainType.CAVE:
                loc = engine.world.get_location_at(x, y)
                if loc and loc.get_property("deepdelve_mouth"):
                    hints.append(
                        f"[TAB] descend into {loc.name} (the Deepdelve)")
            elif dd is not None:
                sec = dd.secret_near((x, y))
                if sec is not None:
                    hints.append(
                        f"[E] search — {sec.get('hint', 'it rings hollow')}")
        except Exception:
            pass

    # Inside somewhere? Leaving is the dominant hint
    if getattr(engine, "current_interior", None):
        hints.append("[TAB] leave the building")
        try:
            from engine.homestead import claimable_here, repairable_here
            if claimable_here(engine) is not None:
                hints.append("[E] buy this derelict home")
            elif repairable_here(engine) is not None:
                hints.append("[E] repair your home (timber + stone)")
        except Exception:
            pass
        try:
            from engine.furniture import piece_near
            piece = piece_near(engine.current_interior,
                               *engine.player.position)
            if piece:
                hints.append(f"[E] {piece['name'].lower()}")
        except Exception:
            pass
        try:
            from engine.rest import can_sleep_here
            if can_sleep_here(engine) is None:
                hints.append("[Enter] sleep until morning")
        except Exception:
            pass
        try:
            allowed, _ = engine.bank.is_at_bank()
            if allowed:
                hints.append("[N] deposit gold  [M] withdraw")
        except Exception:
            pass
    elif getattr(engine, "current_dungeon", None):
        hints.append("[TAB] climb back to the surface")

    try:   # P28.2d a stable sells horses & mules to ride
        from engine import mounts
        if mounts.stable_here(engine) and not mounts.active_mount(engine.player):
            hints.append("[E] stable — buy & ride a mount")
    except Exception:
        pass

    try:   # M.7c a guild hall trains skills (talk to someone → /train)
        gh = getattr(engine, "guildhalls", None)
        if gh is not None and gh.hall_here(engine):
            hints.append("[T] talk · /train a skill here")
    except Exception:
        pass

    try:   # A-board a tavern notice board posts adventuring work
        board = engine.quest_board_at_player()
        if board is not None and engine.quest_board_manager.list_available(board):
            hints.append("[E] read the adventurers' board")
    except Exception:
        pass

    try:   # M5 the build/terraform tool — outdoors, away from a merchant (B there
        # barters). Low priority: shows only when the hint bar has room.
        if not getattr(engine, "current_interior", None) \
                and not getattr(engine, "current_dungeon", None):
            from engine.shop import merchants_near
            if not merchants_near(engine, player, radius=2.0):
                hints.append("[B] build & terraform the land")
    except Exception:
        pass

    try:   # a shut town gate nearby (P31.1d/P37) — never a prison
        tg = getattr(engine, "town_gates", None)
        if tg is not None and not getattr(engine, "current_interior", None):
            g = tg.closed_gate_near(player.position, r=5)
            if g is not None:
                dx, dy = g[0] - x, g[1] - y
                comp = ((("east" if dx > 0 else "west") if abs(dx) >= abs(dy)
                         else ("south" if dy > 0 else "north"))
                        if (dx or dy) else "here")
                if tg.is_locked(g):
                    hints.insert(0, f"[!] the town gate ({comp}) is barred — "
                                    f"raiders! (SHIFT+TAB to force it)")
                else:
                    hints.insert(0, f"[move] the town gate ({comp}) is shut for "
                                    f"the night — walk into it to pass")
    except Exception:
        pass

    try:   # a Wayfarer's waystone underfoot (P37.1)
        tn = getattr(engine, "teleport_network", None)
        if tn is not None and not getattr(engine, "current_interior", None) \
                and tn.platform_at(player.position) is not None:
            if tn.has_ring(player):
                hints.insert(0, "[E] waystone — travel the Wayfarer network")
            else:
                hints.insert(0, "[waystone] you'd need a Wayfarer's Ring")
    except Exception:
        pass

    adjacent = _adjacent_npcs(engine)
    enemies = [n for n in adjacent if _hostile(n)]
    friendly = [n for n in adjacent if not _hostile(n)]

    if enemies:
        hints.append(f"[F] attack {enemies[0].name}")
        try:   # P22.6 quick-cast cue for a caster mid-fight
            from engine.quick_spells import get_slots, ensure_defaults
            ensure_defaults(engine.player)
            if any(get_slots(engine.player)):
                hints.append("[1-5] quick-cast")
        except Exception:
            pass
        try:   # P35.3 terrain telegraph — cover / bad footing shape the fight
            from engine import terrain_combat as tc
            from world.world_map import TerrainType as _T
            p = engine.player
            if tc.cover_score(engine, p.position) > 0:
                hints.insert(0, "[~] you fight from cover — harder to hit")
            elif tc.terrain_at(engine, p.position) in (_T.WATER, _T.SWAMP):
                hints.insert(0, "[!] treacherous footing — your blows go wild")
        except Exception:
            pass
        try:
            from engine.combat_depth import action_name
            move = action_name(engine)
            if move:
                hints.append(f"[SHIFT+V] {move}")
        except Exception:
            pass
        hints.append("[SHIFT+T/I/B] trip · demoralize · feint")
        try:   # I3 grapple → throw (wrestling / throwing)
            from engine import tactics
            if tactics.is_grappling(engine):
                hints.append("[SHIFT+C] THROW the foe in your grip")
            else:
                hints.append("[SHIFT+F/C] shove · grapple")
        except Exception:
            pass
    try:
        tid = getattr(engine, "player_target_id", None)
        lock = engine.npc_manager.npcs.get(tid) if tid else None
        if lock is not None and lock.is_active():
            hints.append(f"[R] shoot {lock.name} · [ [/] ] switch "
                         f"· click to target")
    except Exception:
        pass
    if friendly:
        npc = friendly[0]
        hints.append(f"[T] talk to {npc.name}")
        try:
            if npc.id in engine.companion_manager.party:
                hints.append(f"[P] dismiss {npc.name}")
            elif not engine.companion_manager.can_recruit(npc):
                hints.append(f"[P] invite {npc.name} to your party")
        except Exception:
            pass
        try:
            from engine.shop import merchants_near
            if merchants_near(engine, player, radius=2.0):
                hints.append("[B] barter")
        except Exception:
            pass

    # Ground items
    try:
        items_here = engine.world.ground_items.get((x, y)) or []
        if items_here:
            name = getattr(items_here[0], "name", str(items_here[0]))
            hints.append(f"[G] pick up {name}")
    except Exception:
        pass

    # Terrain / location interactions (only when outside)
    if not getattr(engine, "current_interior", None) and \
            not getattr(engine, "current_dungeon", None):
        try:
            from world.world_map import TerrainType
            terrain = engine.world.map.get_terrain_at(x, y)
            if terrain == TerrainType.CAVE:
                loc = engine.world.get_location_at(x, y)
                # A Deepdelve mouth's descend cue is added high-priority above.
                if not (loc and loc.get_property("deepdelve_mouth")):
                    hints.append("[TAB] descend into the cave")
        except Exception:
            pass
        try:
            loc = engine.world.get_location_at(x, y)
            if loc and loc.name in getattr(engine, "interiors", {}):
                hints.append(f"[TAB] enter {loc.name}")
            if loc and loc.properties.get("forge"):
                hints.append("[K] craft at the forge")
        except Exception:
            pass
        try:
            ok, bank_name = engine.bank.is_at_bank()
            if ok:
                hints.append("[N] deposit gold / [M] withdraw")
        except Exception:
            pass
        try:
            if engine.farm_manager.state_at(x, y) == "mature":
                hints.append("[Z] harvest the ripe wheat")
        except Exception:
            pass
        try:
            loc = engine.world.get_location_at(x, y)
            lname = (loc.name if loc else "").lower()
            if "shrine" in lname or "temple" in lname:
                hints.append("[SHIFT+P] pray")
        except Exception:
            pass
        try:   # a body on your shoulder or at your feet (P13.2)
            from engine.ransom import _body_here, carrying
            if carrying(engine) is not None:
                hints.insert(0, "[SHIFT+G] set them down "
                                "(priest=rescue · fence=ransom)")
            elif _body_here(engine)[0] is not None:
                hints.append("[SHIFT+G] carry them")
        except Exception:
            pass
        try:   # a hungry pet at your heels (P12.14)
            if engine.pet_system.active_pet() is not None and \
                    engine.pet_system.tameness() <= 5:
                hints.append("[SHIFT+Z] toss your pet a treat — "
                             "the bond is fraying")
        except Exception:
            pass
        try:   # tired in the wilds? camp (P12.6)
            from characters.needs import get_fatigue
            if get_fatigue(engine.player) >= 60:
                hints.append("[Enter] make camp (burns provisions)")
        except Exception:
            pass
        try:   # what's broken (P15.9)
            from engine.wounds import status_line
            wl = status_line(engine.player)
            if wl:
                hints.insert(0, wl)
        except Exception:
            pass
        try:   # the infection race (P12.12)
            from engine.infection import hint as _inf_hint
            line = _inf_hint(engine)
            if line:
                hints.insert(0, line)
        except Exception:
            pass
        try:   # needs telegraphs (P12.3)
            from characters.needs import (exhaustion_level, get_thirst,
                                          THIRST_PARCHED)
            if get_thirst(engine.player) >= THIRST_PARCHED:
                hints.insert(0, "[!] parched — drink ([E] by water)")
            lvl = exhaustion_level(engine.player)
            if lvl >= 2:
                hints.insert(0, f"[!] exhaustion {lvl}/6 — you need "
                                f"real sleep")
        except Exception:
            pass
        try:   # in deep water, the only hint that matters (P11.2)
            from characters.status_effects import has_effect
            from world.world_map import TerrainType as TT
            wmap = engine.world.map
            if has_effect(engine.player, "flying"):
                hints.insert(0, "[~] flying — the ground can't "
                                "touch you")
            elif wmap.terrain[y][x] == TT.WATER and \
                    not engine.traversal.is_shallow(x, y) and \
                    not has_effect(engine.player, "water_walking"):
                from engine.hazards import flow_at
                pull = (" — the current pulls!"
                        if flow_at(engine, x, y) else "")
                breath = engine.player.metadata.get("breath")
                if breath is not None and breath > 0:
                    hints.insert(0, f"[~] diving — breath {breath}"
                                    f"{pull}")
                else:
                    hints.insert(0, f"[!] deep water: reach "
                                    f"land{pull}")
        except Exception:
            pass
        try:   # traversal (P11.1): what would a bump cost here?
            from world.world_map import TerrainType as TT
            wmap = engine.world.map
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                tx, ty = x + dx, y + dy
                if not (0 <= tx < wmap.width and
                        0 <= ty < wmap.height):
                    continue
                t = wmap.terrain[ty][tx]
                if t == TT.WATER:
                    if engine.traversal.is_shallow(tx, ty):
                        hints.append("[move] wade the shallows")
                    else:
                        hints.append("[move] swim (Swimming check)")
                    break
                if t == TT.MOUNTAIN:
                    hints.append("[move] climb (Agility check)")
                    break
        except Exception:
            pass
        try:
            from engine.earthworks import has_pickaxe
            from world.world_map import TerrainType
            wmap = engine.world.map
            if any(engine.tile_damage.depth_at(x + dx, y + dy) > 0
                   for dx, dy in ((0, 0), (1, 0), (-1, 0),
                                  (0, 1), (0, -1))):
                hints.append("[E] clear the rubble")
            elif has_pickaxe(engine.player) and any(
                    0 <= x + dx < wmap.width
                    and 0 <= y + dy < wmap.height
                    and wmap.terrain[y + dy][x + dx] ==
                    TerrainType.MOUNTAIN
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                hints.append("[E] dig at the rock face")
        except Exception:
            pass
        try:
            node = engine.gathering_manager.node_at(x, y)
            if node is not None and engine.gathering_manager.has_tool_for(node):
                _, spec, _ = node
                hints.append(f"[Z] {spec['verb']} here")
            elif engine.forage_manager.can_forage(x, y):
                hints.append("[Z] forage for herbs")
            elif node is not None:
                _, spec, _ = node
                hints.append(f"(you'd need {spec['tool_name']} to "
                             f"{spec['verb']} here)")
        except Exception:
            pass

    try:   # winded from sprinting (P34.16)
        from engine import stamina
        if stamina.is_winded(engine.player):
            hints.insert(0, "[!] winded — walk a while to catch your breath")
    except Exception:
        pass

    # Movement flourishes (P34.9) + a standing reminder that the full controls
    # list is one key away (PUX.3) — only when nothing more urgent needs the slot.
    hints.append("[SHIFT+move] run  ·  [`] jump  ·  [.] pace")
    hints.append("[?] all controls")

    # Dedup preserving order, cap (T3.3: a wider cap mid-fight so the combat
    # verbs — trip/demoralize/feint/grapple/shove/weapon-action — actually show)
    cap = COMBAT_HINTS if enemies else MAX_HINTS
    seen = set()
    out = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
        if len(out) >= cap:
            break
    return out
