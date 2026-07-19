"""M.6b — rival adventuring COMPANIES (the first tested sub-step).

The world's other heroes (`engine/adventurers.py`) each roam solo. Here
the seeking, un-recruited ones who hail from the SAME settlement band
together into a COMPANY led by the strongest of them. The followers then
travel WITH their leader — a rival party of their own out in the world —
and the company keeps a RENOWN score that rises as its members grow, the
seed of the renown race against the player.

Pure over the adventurer system: all state lives on the adventurers'
`metadata` (`company` = leader id, `company_leader` = the flag, plus a
`company_name`), so it rides the normal NPC save with no new persistence.

Remainder (M.6b, noted in DEVELOPMENT_PLAN.md): companies take their own
QUESTS and clear dungeons, COMPETE with the player for named hoards, and a
full fortune arc — a company that is wiped loses its renown for good.
"""

import logging

logger = logging.getLogger("llm_rpg.companies")

RENOWN_PER_LEVEL = 10          # a company's renown = Σ member levels × this

_ADJ = ["Iron", "Silver", "Crimson", "Grey", "Bold", "Free",
        "Wandering", "Ember"]
_NOUN = ["Company", "Band", "Blades", "Wardens", "Cohort", "Fellows",
         "Vanguard", "Company"]


def company_name(leader) -> str:
    """A stable, save-safe name derived from the leader's id (no RNG, so it
    survives a reload unchanged)."""
    h = sum(ord(c) for c in str(getattr(leader, "id", "")))
    return f"The {_ADJ[h % len(_ADJ)]} {_NOUN[(h // 7) % len(_NOUN)]}"


def _npcs(advsys):
    return advsys.engine.npc_manager.npcs


def _party(advsys):
    return getattr(getattr(advsys.engine, "companion_manager", None),
                   "party", {}) or {}


def members(advsys, leader_id):
    """The living adventurers (leader included) flying a company's banner."""
    npcs = _npcs(advsys)
    out = []
    for aid in advsys.controllers:
        adv = npcs.get(aid)
        if adv is not None and adv.is_active() \
                and adv.metadata.get("company") == leader_id:
            out.append(adv)
    return out


def renown(advsys, leader_id) -> int:
    """A comparable score for the renown race — the summed levels of the
    company's living members, weighted."""
    return sum(getattr(m, "level", 1)
               for m in members(advsys, leader_id)) * RENOWN_PER_LEVEL


def companies(advsys):
    """Leader ids of every standing company."""
    npcs = _npcs(advsys)
    return [aid for aid in advsys.controllers
            if (npcs.get(aid) is not None and npcs[aid].is_active()
                and npcs[aid].metadata.get("company_leader"))]


def _free_seekers(advsys):
    """Living, un-recruited adventurers not already in a company — the pool
    that can band together."""
    npcs, party = _npcs(advsys), _party(advsys)
    out = []
    for aid in advsys.controllers:
        adv = npcs.get(aid)
        if adv is None or not adv.is_active():
            continue
        if aid in party:                    # a hero's companion, not free
            continue
        if adv.metadata.get("company"):     # already banded
            continue
        out.append(adv)
    return out


def dissolve(advsys) -> int:
    """Disband any company whose LEADER has fallen (or been recruited away):
    the survivors go back to seeking a new band. Returns companies dissolved."""
    npcs, party = _npcs(advsys), _party(advsys)
    dead = 0
    for aid in list(advsys.controllers):
        adv = npcs.get(aid)
        if adv is None:
            continue
        lid = adv.metadata.get("company")
        if not lid:
            continue
        leader = npcs.get(lid)
        broken = (leader is None or not leader.is_active() or lid in party)
        if broken and lid != aid:           # a follower of a broken company
            adv.metadata.pop("company", None)
            adv.metadata.pop("company_leader", None)
            adv.metadata["seeking_party"] = True
        elif broken and lid == aid and lid in party:
            # the leader itself was recruited — stand the company down
            adv.metadata.pop("company_leader", None)
            dead += 1
    return dead


def form(advsys) -> int:
    """Band free seekers who share a home settlement into led companies
    (2+ needed). The highest-level becomes the leader. Idempotent — a member
    already in a company is skipped. Returns the number of NEW companies."""
    groups = {}
    for adv in _free_seekers(advsys):
        key = (adv.metadata.get("home_settlement") or "").strip().lower()
        if not key:
            continue
        groups.setdefault(key, []).append(adv)
    formed = 0
    for band in groups.values():
        if len(band) < 2:
            continue
        band.sort(key=lambda a: (getattr(a, "level", 1), a.id), reverse=True)
        leader = band[0]
        leader.metadata["company_leader"] = True
        leader.metadata["company"] = leader.id
        leader.metadata.setdefault("company_name", company_name(leader))
        leader.metadata["seeking_party"] = False
        for m in band[1:]:
            m.metadata["company"] = leader.id
            m.metadata["seeking_party"] = False
        _announce(advsys, leader, band)
        formed += 1
    return formed


def leader_position(advsys, adv):
    """Where a follower should trail — its leader's tile, or None if it IS
    the leader (leaders roam free) or the leader is gone."""
    lid = adv.metadata.get("company")
    if not lid or lid == adv.id:
        return None
    leader = _npcs(advsys).get(lid)
    if leader is None or not leader.is_active():
        return None
    return tuple(leader.position)


def _announce(advsys, leader, band) -> None:
    try:
        names = ", ".join(m.name for m in band[1:])
        advsys.engine.memory_manager.add_event(
            f"[Realm] {leader.metadata['company_name']} forms — "
            f"{leader.name} leads {names} out to seek their fortune.")
    except Exception:
        pass


# ---- T4.2 the fortune arc: a win-ledger, hoard competition, and death ----

CLAIM_CADENCE = 6              # every N days the top company claims a far lair
RENOWN_TO_CLAIM = 40          # a company must be this renowned to raid a lair


def _ledger(advsys) -> dict:
    """The persisted renown record keyed by leader id (rides the save on
    the player's metadata) — the seed of a real renown race."""
    return advsys.engine.player.metadata.setdefault("company_ledger", {})


def _strongest(advsys):
    best, br = None, -1
    for lid in companies(advsys):
        r = renown(advsys, lid)
        if r > br:
            best, br = lid, r
    return best, br


def run_day(advsys, day: int = 0) -> None:
    """Nightly: refresh each company's peak renown, mark a WIPED company
    fallen (its renown passes into memory), and — periodically — let the
    strongest company beat the player to a far hoard."""
    ledger = _ledger(advsys)
    npcs = _npcs(advsys)
    # 1. register + refresh standing companies
    for lid in companies(advsys):
        adv = npcs.get(lid)
        name = adv.metadata.get("company_name", company_name(adv))
        e = ledger.setdefault(lid, {"name": name, "peak": 0, "fate": "active"})
        e["name"] = name
        e["peak"] = max(e["peak"], renown(advsys, lid))
        if not members(advsys, lid):
            e["fate"] = "active"          # a leader with no band yet still forms
    # 2. a company that HAD a banner but has no living members left has DIED
    for lid, e in ledger.items():
        if e.get("fate") != "active":
            continue
        leader = npcs.get(lid)
        if leader is None or not leader.is_active():
            if not members(advsys, lid):
                e["fate"] = "fallen"
                _announce_fall(advsys, e["name"])
    # 3. compete for hoards — the renown race with the player
    if day and day % CLAIM_CADENCE == 0:
        lid, r = _strongest(advsys)
        if lid is not None and r >= RENOWN_TO_CLAIM:
            lairs = getattr(advsys.engine, "lairs", None)
            name = npcs[lid].metadata.get("company_name", "A rival company")
            if lairs is not None:
                try:
                    lairs.claim_by_rival(name)
                except Exception:
                    pass


def _announce_fall(advsys, name: str) -> None:
    try:
        advsys.engine.memory_manager.add_event(
            f"[Realm] {name} is wiped out to the last — its renown passes "
            f"into memory, a cautionary tale in the tap-rooms.")
    except Exception:
        pass


def ledger_lines(advsys) -> list:
    """The renown race, for the Y-journal / realm digest."""
    ledger = _ledger(advsys)
    if not ledger:
        return []
    active = sorted((e for e in ledger.values() if e.get("fate") == "active"),
                    key=lambda e: -e.get("peak", 0))
    out = []
    if active:
        out.append("Rival companies (the renown race):")
        for e in active[:3]:
            out.append(f"  {e['name']} — renown {e.get('peak', 0)}")
    fallen = [e for e in ledger.values() if e.get("fate") == "fallen"]
    if fallen:
        out.append(f"  Companies fallen: {len(fallen)}")
    return out
