"""NPC families + relationships.

Each NPC may have parents, siblings, and a spouse — encoded as ids.
These power gossip and dialog flavor. Defined as a static registry
since presets are fixed.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Family:
    npc_id: str
    parents: List[str] = field(default_factory=list)
    siblings: List[str] = field(default_factory=list)
    spouse: Optional[str] = None
    children: List[str] = field(default_factory=list)
    surname: str = ""


# Pre-defined family ties for preset NPCs ------------------------------

FAMILIES: Dict[str, Family] = {
    "tavernkeeper_01": Family(
        npc_id="tavernkeeper_01", surname="Brindle",
        spouse="hamlet_innkeeper_01",   # married to Esra
        siblings=["minstrel_01"],        # brother of Melody
    ),
    "minstrel_01": Family(
        npc_id="minstrel_01", surname="Brindle",
        siblings=["tavernkeeper_01"],
    ),
    "hamlet_innkeeper_01": Family(
        npc_id="hamlet_innkeeper_01", surname="Brindle",
        spouse="tavernkeeper_01",
    ),
    "blacksmith_01": Family(
        npc_id="blacksmith_01", surname="Stonehammer",
        siblings=["hamlet_wheelwright_01"],   # Durgan and Tova are cousins (siblings here)
    ),
    "hamlet_wheelwright_01": Family(
        npc_id="hamlet_wheelwright_01", surname="Stonehammer",
        siblings=["blacksmith_01"],
    ),
    "guard_01": Family(
        npc_id="guard_01", surname="Vance",
    ),
    "hamlet_priest_01": Family(
        npc_id="hamlet_priest_01", surname="of the Light",
    ),
}


def family_of(npc_id: str) -> Optional[Family]:
    return FAMILIES.get(npc_id)


def relation_to(npc_id: str, other_id: str) -> str:
    """Describe how `other_id` is related to `npc_id`, if at all."""
    fam = FAMILIES.get(npc_id)
    if not fam:
        return ""
    if other_id == fam.spouse:
        return "my spouse"
    if other_id in fam.parents:
        return "my parent"
    if other_id in fam.siblings:
        return "my sibling"
    if other_id in fam.children:
        return "my child"
    return ""
