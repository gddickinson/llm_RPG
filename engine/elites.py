"""The endgame curve — elite variants & party-scaled packs (P19.5).

The wilderness table tops out around level 3-4 while the player climbs to
20, so a strong party met nothing worth drawing a sword for. This scales
the wild to the party WITHOUT re-authoring every monster: when a party
out-levels a fresh wilderness spawn, that spawn may be promoted to an
ELITE — a Dire, a Champion, an Ancient — buffed and retitled, and a
strong party draws not one beast but a warband (the extras share a tag so
the P19.3 pack brain runs them under the elite as their leader; cut the
leader down and the warband breaks).

Pure over `data/elites.json` tiers. Low-level play is untouched: with no
level gap there is no promotion and no warband.
"""

import logging

logger = logging.getLogger("llm_rpg.elites")


def party_level(engine) -> int:
    """The party's effective power: the strongest member, plus a nudge
    for a fuller party (more blades warrant tougher foes)."""
    lvl = engine.player.level
    party = []
    try:
        party = list(engine.companion_manager.party or [])
        for cid in party:
            c = engine.npc_manager.npcs.get(cid)
            if c is not None and c.is_active():
                lvl = max(lvl, c.level)
    except Exception:
        pass
    return lvl + len(party)


def _config() -> dict:
    from items.data_loader import load_data_file
    try:
        return load_data_file("elites.json")
    except Exception as e:
        logger.debug(f"elites.json: {e}")
        return {}


def _best_tier(gap: int, cfg: dict):
    tier = None
    for t in cfg.get("tiers", []):
        if gap >= t.get("min_gap", 999):
            tier = t                       # the highest tier the gap earns
    return tier


def maybe_promote(engine, monster, rng) -> bool:
    """Promote a fresh spawn to an elite if the party out-levels it.
    Returns True if promoted."""
    cfg = _config()
    gap = party_level(engine) - monster.level
    tier = _best_tier(gap, cfg)
    if tier is None:
        return False
    if rng.random() > tier.get("chance", 0.3):
        return False
    apply_tier(monster, tier)
    return True


def apply_tier(monster, tier) -> None:
    monster.name = tier.get("title", "{name}").replace("{name}", monster.name)
    monster.max_hp = int(monster.max_hp * tier.get("hp_mult", 1.5))
    monster.hp = monster.max_hp
    monster.level += tier.get("level_bonus", 2)
    try:
        monster.strength += tier.get("str_bonus", 2)
    except Exception:
        pass
    monster.metadata["elite"] = True


def extra_pack(engine, base_level: int, rng) -> int:
    """How many EXTRA beasts join a spawn for a party that out-levels it."""
    cfg = _config()
    gap = party_level(engine) - base_level
    if gap < cfg.get("pack_min_gap", 3):
        return 0
    if rng.random() > cfg.get("pack_chance", 0.5):
        return 0
    return min(1 + gap // 4, cfg.get("pack_extra_max", 3))
