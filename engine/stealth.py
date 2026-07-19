"""Stealth & sneak attacks (GAP.3) — make the rogue's art matter.

The STEALTH skill was vestigial: no detection, no sneak attacks. This
adds both, ENTIRELY gated on the opt-in CRAWL stance (`.` key →
`_move_mode == "crawl"`), so default play — and every existing pursuit /
aggression / combat test — is untouched.

While crawling, a hostile only NOTICES the player inside a detection
radius that shrinks with the player's Dexterity, level, rogue calling and
the dark; a hostile that has not noticed you is UNAWARE, and a strike on
an unaware foe lands as a SNEAK ATTACK for heavy bonus damage. An
un-noticed hostile is skipped by pursuit + aggression, so a stealthy
player can creep up — or slip past.

Awareness lives in `npc.metadata["noticed_player"]`. Pure helpers; the
combat / pursuit / aggression hooks call in.
"""

_ROGUISH = {"rogue", "ranger", "assassin", "thief", "scout", "hunter"}
BASE_DETECT = 7


def is_sneaking(player) -> bool:
    return (getattr(player, "metadata", None) or {}).get(
        "_move_mode") == "crawl"


def _cheb(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _dex_mod(char) -> int:
    dex = getattr(char, "dexterity", None)
    if dex is None:
        dex = (getattr(char, "stats", {}) or {}).get("dexterity", 10)
    return (dex - 10) // 2


def _is_roguish(char) -> bool:
    return getattr(getattr(char, "character_class", None), "value", "") \
        in _ROGUISH


def _stealth_prof(char) -> int:
    """A small bonus if the character is trained in the Stealth skill."""
    try:
        skills = (getattr(char, "metadata", {}) or {}).get("skills", {})
        if "stealth" in skills or "stealth" in (
                getattr(char, "proficiencies", []) or []):
            return 2
    except Exception:
        pass
    return 0


def evasion_rating(char) -> int:
    """How much the sneaker SHRINKS a watcher's detection radius."""
    return (_dex_mod(char) + getattr(char, "level", 1) // 3
            + (3 if _is_roguish(char) else 0) + _stealth_prof(char))


def sneak_power(char) -> int:
    """How hard a sneak attack hits (offensive stealth)."""
    return (getattr(char, "level", 1) + _dex_mod(char)
            + (4 if _is_roguish(char) else 0) + _stealth_prof(char))


def detection_radius(engine, target) -> int:
    """The range at which `target` notices the crawling player, given the
    player's evasion and the dark. Never below 1 (adjacent = seen)."""
    red = evasion_rating(engine.player)
    try:
        if engine.world.time_of_day() == "night":
            red += 2
    except Exception:
        pass
    if getattr(engine, "current_dungeon", None):
        red += 2
    return max(1, BASE_DETECT - red)


def _has_los(engine, a, b) -> bool:
    try:
        if getattr(engine, "current_dungeon", None) or \
                getattr(engine, "current_interior", None):
            zone = engine.active_zone()
            from world.fov import zone_fov
            return tuple(b) in zone_fov(zone, tuple(a), radius=12)
        from world.fov import overworld_los
        return overworld_los(engine, tuple(a), tuple(b))
    except Exception:
        return True                       # unsure → assume seen (safe)


def detects(engine, target) -> bool:
    """Does `target` notice the crawling player this turn?"""
    if _cheb(target.position, engine.player.position) > \
            detection_radius(engine, target):
        return False
    return _has_los(engine, target.position, engine.player.position)


def evades(engine, target) -> bool:
    """True if the player is currently HIDDEN from `target` — sneaking,
    not yet noticed, and outside its detection. Pursuit/aggression skip a
    target that the player evades. False whenever not sneaking, so default
    play is unchanged."""
    player = engine.player
    if not is_sneaking(player):
        return False
    if (getattr(target, "metadata", None) or {}).get("noticed_player"):
        return False
    return not detects(engine, target)


def is_unaware(target) -> bool:
    return not (getattr(target, "metadata", None) or {}).get(
        "noticed_player")


def note_engaged(target) -> None:
    if getattr(target, "metadata", None) is None:
        target.metadata = {}
    target.metadata["noticed_player"] = True


def forget(target) -> None:
    (getattr(target, "metadata", None) or {}).pop("noticed_player", None)


def mark_combat_awareness(engine, attacker, defender) -> None:
    """Blows have been exchanged — the NPC now knows where the player is."""
    player = engine.player
    if attacker is player:
        note_engaged(defender)
    elif defender is player:
        note_engaged(attacker)


def apply_sneak_bonus(attacker, damage):
    """The pure damage boost of a confirmed sneak attack (+60%..+250%,
    scaled by the attacker's sneak power)."""
    power = sneak_power(attacker)
    mult = min(2.5, 0.6 + 0.07 * max(0, power))
    return damage + int(damage * mult)


def sneak_attack(engine, attacker, defender, damage):
    """If the PLAYER strikes an UNAWARE foe, return boosted damage and
    True; otherwise the damage unchanged and False. (Reads awareness — the
    combat hook captures it BEFORE marking the fight joined, then uses
    `apply_sneak_bonus`.)"""
    if attacker is not engine.player or defender is engine.player:
        return damage, False
    if not is_sneaking(attacker) or not is_unaware(defender):
        return damage, False
    return apply_sneak_bonus(attacker, damage), True
