"""Necromancy (George): the power to RAISE the dead into your service, to
COMMAND them, and — for the darkest students — to shed life itself and
join the undead as a lich. The counter-power (Turn/destroy Undead) lives
in `engine/undead`; this is the create/command/become half.

A raised minion is a friendly undead Character added to the party (reusing
the companion follow-and-fight AI — a skeleton walks and fights for free).
The gods take note: the Pale Lady (death) smiles on the raiser, Solara
(the sun) turns her face away. State on `player.metadata`; minions ride the
NPC save as party members.
"""

import logging

logger = logging.getLogger("llm_rpg.necromancy")

MINION_TEMPLATE = {"zombie": "zombie", "skeleton": "skeleton_warrior"}


def is_necromancer(character) -> bool:
    known = (getattr(character, "metadata", None) or {}).get("spells_known", [])
    return ("animate_dead" in known
            or (character.metadata or {}).get("specialization") == "necromancer")


def minion_cap(caster) -> int:
    return 2 + max(0, getattr(caster, "level", 1) // 4)


def minions(engine, caster):
    party = getattr(engine.companion_manager, "party", [])
    out = []
    for cid in party:
        ch = engine.npc_manager.get_npc(cid)
        if ch is not None and (ch.metadata or {}).get("necro_minion") \
                and (ch.metadata or {}).get("owner") == caster.id:
            out.append(ch)
    return out


def _nearby_corpse(engine, caster, r=4):
    """A recently-fallen body near the caster — a dead/KO'd NPC to re-flesh
    as a zombie. (Else the necromancer drags fresh bones from the earth.)"""
    cx, cy = caster.position
    for npc in engine.npc_manager.npcs.values():
        if npc is caster or npc.is_active():
            continue
        if (npc.metadata or {}).get("undead"):
            continue
        nx, ny = npc.position
        if max(abs(nx - cx), abs(ny - cy)) <= r:
            return npc
    return None


def _free_tile(engine, caster):
    from engine.agent_nav import walkable
    cx, cy = caster.position
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        pos = (cx + dx, cy + dy)
        try:
            if walkable(engine, caster, pos):
                return pos
        except Exception:
            pass
    return (cx, cy)


def animate_dead(engine, caster, target=None) -> str:
    """Raise a minion — a zombie from a nearby corpse, else conjured bones."""
    if len(minions(engine, caster)) >= minion_cap(caster):
        return "The dead you already command are all your will can hold."
    corpse = target if (target is not None and not target.is_active()) \
        else _nearby_corpse(engine, caster)
    utype = "zombie" if corpse is not None else "skeleton"
    pos = tuple(corpse.position) if corpse is not None else _free_tile(engine,
                                                                       caster)
    from world.monsters import build_monster
    m = build_monster(MINION_TEMPLATE[utype], pos)
    m.id = f"minion_{caster.id}_{len(minions(engine, caster))}_{utype}"
    m.metadata["necro_minion"] = True
    m.metadata["owner"] = caster.id
    try:
        m.faction = getattr(caster, "faction", "neutral")
    except Exception:
        pass
    m.personality = {"traits": ["loyal"]}
    m.goals = ["Serve the necromancer"]
    if corpse is not None:                    # the body is consumed into the risen
        try:
            engine.npc_manager.remove_npc(corpse.id)
        except Exception:
            pass
    engine.npc_manager.add_npc(m)
    try:
        engine.world.map.place_character(m, *pos)
    except Exception:
        pass
    if m.id not in engine.companion_manager.party:
        engine.companion_manager.party.append(m.id)
    _gods(engine, caster, raised=True)
    engine.memory_manager.add_event(
        f"[Necro] {caster.name} raises {m.name} from the "
        + ("fallen" if corpse is not None else "cold earth")
        + " — it rises to serve.")
    return f"You raise {m.name} to serve you."


def command_undead(engine, caster) -> str:
    """Bend a nearby HOSTILE undead to your will — enthralling it into your
    service (if you have room), else mending the minions you already hold."""
    if len(minions(engine, caster)) < minion_cap(caster):
        from engine.undead import is_undead
        cx, cy = caster.position
        for npc in engine.npc_manager.npcs.values():
            if not npc.is_active() or not is_undead(npc):
                continue
            if (npc.metadata or {}).get("necro_minion"):
                continue
            nx, ny = npc.position
            if max(abs(nx - cx), abs(ny - cy)) <= 4 \
                    and getattr(npc, "level", 1) <= getattr(caster, "level", 1):
                npc.metadata["necro_minion"] = True
                npc.metadata["owner"] = caster.id
                npc.metadata.pop("broken", None)
                try:
                    npc.faction = getattr(caster, "faction", "neutral")
                except Exception:
                    pass
                if npc.id not in engine.companion_manager.party:
                    engine.companion_manager.party.append(npc.id)
                engine.memory_manager.add_event(
                    f"[Necro] {caster.name} bends {npc.name} to their will.")
                return f"{npc.name} bows to your command."
    healed = 0
    for m in minions(engine, caster):
        if m.hp < m.max_hp:
            m.hp = min(m.max_hp, m.hp + 6)
            healed += 1
    if healed:
        return f"You knit your risen dead back together ({healed} mended)."
    return "No undead heed your call here."


# ---- becoming undead ---------------------------------------------------

def become_undead(engine, character, undead_type: str, *, source="") -> str:
    """Turn a LIVING character into undead (a lich's ascension, a vampire's
    embrace, a plague-curse). They keep their form and mind but gain the
    undead nature — no poison touches them, holy light burns."""
    meta = character.metadata
    if meta.get("undead"):
        return f"{character.name} is already among the dead."
    meta["undead"] = True
    meta["undead_type"] = undead_type
    meta["was_living"] = True
    engine.memory_manager.add_event(
        f"[Legend] {character.name} crosses into undeath as "
        f"{undead_type.replace('_', ' ')}"
        + (f" — {source}" if source else "") + ".")
    return f"{character.name} is undead now — {undead_type.replace('_', ' ')}."


def lich_ascension(engine, character) -> str:
    """A master necromancer binds their soul to a phylactery and sheds
    life to become a LICH — deathless, and mightier in the dark arts."""
    if not is_necromancer(character):
        return "This rite is beyond you — you are no necromancer."
    if getattr(character, "level", 1) < 10:
        return "You are not yet mighty enough to survive the crossing."
    msg = become_undead(engine, character, "lich", source="the phylactery rite")
    try:
        from engine.spells import ensure_mana
        character.metadata["max_mana"] = character.metadata.get("max_mana", 0) + 20
        ensure_mana(character)
    except Exception:
        pass
    _gods(engine, character, raised=True)
    return msg + " Your magic deepens, and death holds no more dominion."


def vampire_embrace(engine, character) -> str:
    return become_undead(engine, character, "vampire",
                         source="a vampire's kiss")


def _gods(engine, caster, *, raised=False):
    """The gods weigh necromancy: the Pale Lady (death) warms, Solara (sun)
    cools."""
    if caster is not getattr(engine, "player", None):
        return
    try:
        meta = caster.metadata.setdefault("god_favor", {})
        if raised:
            meta["pale_lady"] = meta.get("pale_lady", 0) + 2
            meta["solara"] = meta.get("solara", 0) - 1
    except Exception:
        pass
