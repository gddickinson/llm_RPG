"""Branching dialog trees for the heuristic provider.

When the LLM is the heuristic provider, conversations can use prewritten
branching menus instead of free text. Each dialog node has a prompt and
a list of (option_text, next_node_id, action) tuples.

`action` can be:
- None: just navigate
- "end": end conversation
- "offer_quest:<id>": offer a quest
- "turn_in:<id>": turn in a quest
- "buy:<item_id>": shop sells an item
- "recruit": invite NPC to join party
- "info:<key>": surface a piece of world info
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DialogOption:
    text: str
    next_node: str = ""
    action: str = ""


@dataclass
class DialogNode:
    prompt: str
    options: List[DialogOption] = field(default_factory=list)


@dataclass
class DialogTree:
    root: str
    nodes: Dict[str, DialogNode] = field(default_factory=dict)


# Templates per NPC class -----------------------------------------------

def _tavernkeeper_tree() -> DialogTree:
    t = DialogTree(root="root")
    t.nodes["root"] = DialogNode(
        prompt="Welcome to the Oakvale Tavern! What'll it be?",
        options=[
            DialogOption("Any rumors?", "rumors"),
            DialogOption("I'd like an ale.", "ale", action="buy:ale"),
            DialogOption("Tell me about yourself.", "about"),
            DialogOption("Goodbye.", "", action="end"),
        ],
    )
    t.nodes["rumors"] = DialogNode(
        prompt="Aye, talk has it a troll roams the east road. The guard "
               "Karim is hunting for someone to deal with him.",
        options=[
            DialogOption("Anything else?", "rumors2"),
            DialogOption("Back.", "root"),
        ],
    )
    t.nodes["rumors2"] = DialogNode(
        prompt="The cleric at the temple needs herbs — coin's good if "
               "you have a forager's hand.",
        options=[DialogOption("Back.", "root")],
    )
    t.nodes["ale"] = DialogNode(
        prompt="One ale, on the house — first one's always free for newcomers.",
        options=[DialogOption("Thanks.", "root")],
    )
    t.nodes["about"] = DialogNode(
        prompt="Goren's the name. Been pouring ale here for twenty years. "
               "Saw a strange traveler last week — silver hair, eyes like ice.",
        options=[DialogOption("Back.", "root")],
    )
    return t


def _merchant_tree() -> DialogTree:
    t = DialogTree(root="root")
    t.nodes["root"] = DialogNode(
        prompt="Welcome to my shop. Looking to buy or sell?",
        options=[
            DialogOption("Buy a healing potion (20g).", "", action="buy:potion"),
            DialogOption("Buy bandages (5g).", "", action="buy:bandage"),
            DialogOption("Any rumors?", "rumors"),
            DialogOption("Goodbye.", "", action="end"),
        ],
    )
    t.nodes["rumors"] = DialogNode(
        prompt="Trade's been slow with the bandits on the road. If you "
               "clear them out, my prices may improve.",
        options=[DialogOption("Back.", "root")],
    )
    return t


def _guard_tree() -> DialogTree:
    t = DialogTree(root="root")
    t.nodes["root"] = DialogNode(
        prompt="Halt. You're new here. State your business.",
        options=[
            DialogOption("I'm an adventurer.", "adventurer"),
            DialogOption("Do you have work for me?", "quest",
                         action="offer_quest:troll_hunt"),
            DialogOption("Any news?", "news"),
            DialogOption("Goodbye.", "", action="end"),
        ],
    )
    t.nodes["adventurer"] = DialogNode(
        prompt="Adventurer, eh? Keep your blade sheathed in town. "
               "Out east is where the trouble lies.",
        options=[DialogOption("Back.", "root")],
    )
    t.nodes["quest"] = DialogNode(
        prompt="A troll named Gorkash robs travelers on the east road. "
               "Deal with him and you'll have my gratitude — and gold.",
        options=[DialogOption("Back.", "root")],
    )
    t.nodes["news"] = DialogNode(
        prompt="Strange lights in the mountains three nights running. "
               "Could be brigands. Could be worse.",
        options=[DialogOption("Back.", "root")],
    )
    return t


def _bard_tree() -> DialogTree:
    t = DialogTree(root="root")
    t.nodes["root"] = DialogNode(
        prompt="Ah, a fresh face! Care for a song?",
        options=[
            DialogOption("Sing me a tale.", "song"),
            DialogOption("Want to travel with me?", "join", action="recruit"),
            DialogOption("Goodbye.", "", action="end"),
        ],
    )
    t.nodes["song"] = DialogNode(
        prompt="*strums lute* 'Beneath the moon the troll did roam, "
               "till came a hero seeking home...'",
        options=[DialogOption("Lovely.", "root")],
    )
    t.nodes["join"] = DialogNode(
        prompt="Adventure with you? I might — if you've proven yourself.",
        options=[DialogOption("Back.", "root")],
    )
    return t


def _cleric_tree() -> DialogTree:
    t = DialogTree(root="root")
    t.nodes["root"] = DialogNode(
        prompt="Light bless you, traveler. How may the temple serve?",
        options=[
            DialogOption("I need healing.", "heal"),
            DialogOption("Do you have work?", "work",
                         action="offer_quest:herb_gathering"),
            DialogOption("Goodbye.", "", action="end"),
        ],
    )
    t.nodes["heal"] = DialogNode(
        prompt="Pray here and your wounds will mend in time.",
        options=[DialogOption("Back.", "root")],
    )
    t.nodes["work"] = DialogNode(
        prompt="Our stocks of healing herbs run low. If you gather some, "
               "I'll reward you well.",
        options=[DialogOption("Back.", "root")],
    )
    return t


_TREE_BY_CLASS = {
    "merchant": _merchant_tree,
    "guard": _guard_tree,
    "bard": _bard_tree,
    "cleric": _cleric_tree,
}

# Specific NPC id overrides (e.g. tavernkeeper has a richer tree)
_TREE_BY_NPC_ID = {
    "tavernkeeper_01": _tavernkeeper_tree,
}


def tree_for(npc) -> Optional[DialogTree]:
    """Return the dialog tree applicable to this NPC, or None."""
    if npc.id in _TREE_BY_NPC_ID:
        return _TREE_BY_NPC_ID[npc.id]()
    klass = getattr(npc.character_class, "value", "")
    factory = _TREE_BY_CLASS.get(klass)
    if factory:
        return factory()
    return None
