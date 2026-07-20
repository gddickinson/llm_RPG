"""Away-agent SOCIAL behaviour (George: an away-hero should live a rich life —
talk to NPCs, take quests, form parties — not wander in a circle). Split from
`agent_controller` to hold the 500-line line and make room for smarter people-
seeking. Functions take the controller as `ctrl` so they read/write its
`greeted` / `_greets` / `recent` / party state.

Key idea: prefer a friendly with real BUSINESS (a quest to give, a recruit, a
trade) over a random townsperson — otherwise, in a crowded town, the hero would
only ever say hello to the nearest passer-by and never reach the adventurer one
tile further on who would JOIN it.
"""

from engine import agent_nav as nav
from engine import agent_goals as agoals
from engine import agent_trade as agtrade
from engine import agent_sense as sense
from engine.agent_nav import _dist

GREET_CAP = 3          # mere hellos per window before the hero moves ON


def offers(ctrl, engine, char, friend) -> bool:
    """Real BUSINESS with `friend` — an untaken quest, a recruitable ally, or a
    merchant we've goods to trade — worth walking over for even after a hello."""
    qm = getattr(engine, "quest_manager", None)
    try:
        if qm and qm.offered_by(friend.id):
            return True
        from engine.conversation import is_merchant
        if is_merchant(friend) and agtrade.wants_to_trade(engine, char, friend):
            return True
        return ctrl._room_in_party(engine) and \
            engine.companion_manager.can_recruit(friend) == ""
    except Exception:
        return False


def _should_recruit_first(ctrl, engine) -> bool:
    """A PARTYLESS hero (with room) forms a band before committing to a big
    quest it would die soloing — while any adventurer is still there to join."""
    try:
        if not ctrl._room_in_party(engine) or engine.companion_manager.party:
            return False
        cm = engine.companion_manager
        return any(n.metadata.get("adventurer") and n.is_active()
                   and cm.can_recruit(n) == ""
                   for n in engine.npc_manager.npcs.values())
    except Exception:
        return False


def _pick_friend(ctrl, engine, char, reach):
    """The friendly worth engaging: the nearest one with BUSINESS if any is in
    reach, else simply the nearest face (for a hello)."""
    friends = sense.friendlies_near(engine, char, r=reach)
    if not friends:
        return None
    business = [f for f in friends if offers(ctrl, engine, char, f)]
    if business:
        # among those with business, prefer the STRONGEST RECRUIT (gather a
        # capable band that can clear adventures, not the weakest three that
        # happen to be nearest); other business keeps its nearest-first order
        recruitable = [f for f in business if f.metadata.get("adventurer")]
        if recruitable:
            return max(recruitable, key=lambda f: getattr(f, "level", 1))
        return business[0]
    return friends[0]


def social_plan(ctrl, engine, char, disp):
    """Near someone worth it? Take their quest, recruit them, or say hello —
    biased by disposition (a SOCIABLE hero seeks people out)."""
    outgoing = disp == "sociable" or agoals.ambition(char) == "fellowship"
    reach = 8 if outgoing else 5
    friend = _pick_friend(ctrl, engine, char, reach)
    if friend is None:
        # nobody engaging within reach — but a PARTYLESS hero actively walks
        # to the nearest recruitable adventurer (tracking its LIVE position, so
        # a roaming band is still caught) to form a party before adventuring
        return _seek_recruit(ctrl, engine, char)
    if _dist(char.position, friend.position) <= 1:
        # HIGH-VALUE business always draws the hero
        from engine.conversation import is_merchant
        if is_merchant(friend) \
                and agtrade.wants_to_trade(engine, char, friend):
            return ("trade", friend)
        qm = getattr(engine, "quest_manager", None)
        offered = qm.offered_by(friend.id) if qm else []
        if offered and not _should_recruit_first(ctrl, engine):
            return ("accept_quest", offered[0], friend)
        if ctrl._room_in_party(engine):
            try:
                if engine.companion_manager.can_recruit(friend) == "":
                    return ("recruit", friend)
            except Exception:
                pass
        # a mere hello — only until socially SATIATED, so the hero doesn't
        # spend its life greeting a crowded town instead of getting out to
        # quest/recruit/explore; it socialises again after SATIATE_WINDOW.
        if friend.id not in ctrl.greeted and ctrl._greets < GREET_CAP:
            ctrl._greets += 1
            return ("talk", friend)
        return None
    # walk to someone with real BUSINESS always; to say hello only unsated
    if offers(ctrl, engine, char, friend) \
            or (friend.id not in ctrl.greeted and ctrl._greets < GREET_CAP):
        return ("move", nav.safe_step(engine, char, friend.position,
                                      ctrl.recent))
    return _seek_recruit(ctrl, engine, char)


def _seek_recruit(ctrl, engine, char):
    """A partyless hero walks toward the nearest recruitable adventurer's LIVE
    position — the point of a rich life is a band to run the world with."""
    if not _should_recruit_first(ctrl, engine):
        return None
    tgt = agoals.nearest_recruitable(ctrl, engine, char)
    if tgt is None:
        return None
    step = nav.safe_step(engine, char, tgt[1], ctrl.recent)
    return ("move", step) if step != (0, 0) else None
