"""M.10c — how freely a character gives AID depends on WHO they are.

George: different characters, with different alignments, alliances and
enmities, act differently in a party — some are less willing to help a
particular ally or the hero than others; their personalities and standing
relationships drive it, in a party and out.

A single `aid_willingness` score (0–100) gates the share/heal decisions.
It is driven by the RELATIONSHIP the giver holds toward the one in need
(the biggest lever), the giver's personality TRAITS (generous vs stingy),
and its ALIGNMENT (a good soul helps freely; a wicked one hoards). Pure
functions over the Character — no state, no side effects.
"""

BASE = 50                 # a neutral stranger's baseline willingness

_GENEROUS = {"loyal", "kind", "generous", "friendly", "brave", "cheerful",
             "honest", "compassionate", "noble", "selfless"}
_STINGY = {"selfish", "greedy", "grumpy", "suspicious", "stubborn", "cruel",
           "cowardly", "callous", "spiteful"}


def _traits(char):
    p = getattr(char, "personality", None) or {}
    return {str(t).lower() for t in p.get("traits", [])}


def _alignment(char) -> str:
    m = getattr(char, "metadata", {}) or {}
    p = getattr(char, "personality", None) or {}
    return str(m.get("alignment") or p.get("alignment") or "").lower()


def aid_willingness(giver, recipient) -> int:
    """How freely `giver` will spend a resource to help `recipient` (0–100).
    You always help yourself (100). Otherwise: relationship + trait lean +
    alignment lean, off a neutral baseline."""
    if giver is recipient or \
            getattr(giver, "id", 1) == getattr(recipient, "id", 2):
        return 100
    score = BASE
    try:
        score += int(giver.get_relationship(getattr(recipient, "id", "")))
    except Exception:
        pass
    traits = _traits(giver)
    if traits & _GENEROUS:
        score += 15
    if traits & _STINGY:
        score -= 20
    align = _alignment(giver)
    if "good" in align:
        score += 15
    elif "evil" in align:
        score -= 25
    return max(0, min(100, score))


def will_aid(giver, recipient, threshold: int = 45) -> bool:
    """True if the giver is willing enough to help the recipient. The default
    threshold sits just below neutral, so a stranger of no strong feeling
    still lends a hand, but a soured or selfish one won't."""
    return aid_willingness(giver, recipient) >= threshold
