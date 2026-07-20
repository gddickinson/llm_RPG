"""T2.5 — realised ambitions CHANGE the world.

The ambition system (`engine/ambitions.py`) sets flags — `master`, `prospered`,
`avenged`, `moved_on` — when an NPC realises a life goal, but the world-sim review
found those flags were read NOWHERE: a "master of the craft" was identical to any
villager. These pure helpers let the shop and dialog pay the flags off, so a
realised ambition is tangible: a master crafter forges MASTERWORK stock and earns
a title; a prospered merchant carries a fatter purse (buys more of your loot).
"""


def _meta(npc) -> dict:
    return getattr(npc, "metadata", None) or {}


def is_master(npc) -> bool:
    return bool(_meta(npc).get("master"))


def is_prospered(npc) -> bool:
    return bool(_meta(npc).get("prospered"))


def title_prefix(npc) -> str:
    """A hailed title for a realised NPC ("" if none) — for names/greetings."""
    if is_master(npc):
        return "Master "
    return ""


def shop_gold_bonus(npc) -> int:
    """A prospered merchant's fatter buying purse."""
    return 300 if is_prospered(npc) else 0


# a master crafter's signature MASTERWORK by shop category (rare-tier, sold — the
# epic/legendary ceiling stays loot-only). None = this trade has no masterwork.
_MASTERWORK = {
    "blacksmith": "fortified_plate",
    "smithy": "fortified_plate",
    "general": "banded_mail",
    "ranger": "brigandine",
}


def masterwork_item(npc, category: str):
    """The item id a master of `category` also puts on the shelf, or None."""
    if not is_master(npc):
        return None
    return _MASTERWORK.get(category)
