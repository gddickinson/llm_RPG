"""D&D-style skill system.

Skills map to an ability score (STR/DEX/CON/INT/WIS/CHA). A check is
1d20 + ability modifier vs a difficulty class (DC).
"""

import logging
import random
from enum import Enum
from typing import Tuple

logger = logging.getLogger("llm_rpg.skills")


class Skill(Enum):
    """Skills, paired with the ability score they use."""
    # STR
    ATHLETICS = ("athletics", "strength")
    # DEX
    ACROBATICS = ("acrobatics", "dexterity")
    STEALTH = ("stealth", "dexterity")
    SLEIGHT_OF_HAND = ("sleight_of_hand", "dexterity")
    LOCKPICKING = ("lockpicking", "dexterity")
    # INT
    ARCANA = ("arcana", "intelligence")
    HISTORY = ("history", "intelligence")
    INVESTIGATION = ("investigation", "intelligence")
    NATURE = ("nature", "intelligence")
    # WIS
    INSIGHT = ("insight", "wisdom")
    MEDICINE = ("medicine", "wisdom")
    PERCEPTION = ("perception", "wisdom")
    SURVIVAL = ("survival", "wisdom")
    ANIMAL_HANDLING = ("animal_handling", "wisdom")
    # CHA
    DECEPTION = ("deception", "charisma")
    INTIMIDATION = ("intimidation", "charisma")
    PERFORMANCE = ("performance", "charisma")
    PERSUASION = ("persuasion", "charisma")

    @property
    def ability(self) -> str:
        return self.value[1]

    @property
    def skill_name(self) -> str:
        return self.value[0]


class Difficulty(Enum):
    TRIVIAL = 5
    EASY = 10
    MEDIUM = 15
    HARD = 20
    VERY_HARD = 25
    LEGENDARY = 30


def ability_modifier(score: int) -> int:
    """Standard D&D modifier: (score - 10) // 2 (rounded toward -inf)."""
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """D&D 5e proficiency bonus."""
    return 2 + max(0, (level - 1) // 4)


def roll_check(character, skill: Skill, dc: int = 10,
               proficient: bool = False, advantage: bool = False,
               disadvantage: bool = False,
               rng: random.Random = None) -> Tuple[bool, int, int]:
    """Roll a skill check.

    Returns
    -------
    (success, total, d20_roll)
        success: True if total >= dc
        total: d20 + ability_mod (+ prof if proficient)
        d20_roll: raw d20 value rolled
    """
    rng = rng or random
    if advantage and disadvantage:
        advantage = disadvantage = False  # cancel
    if advantage:
        d20 = max(rng.randint(1, 20), rng.randint(1, 20))
    elif disadvantage:
        d20 = min(rng.randint(1, 20), rng.randint(1, 20))
    else:
        d20 = rng.randint(1, 20)

    ability_score = getattr(character, skill.ability, 10)
    mod = ability_modifier(ability_score)
    prof = proficiency_bonus(getattr(character, "level", 1)) if proficient else 0

    total = d20 + mod + prof
    success = total >= dc

    logger.debug(
        f"{getattr(character, 'name', '?')} {skill.skill_name} check: "
        f"d20={d20} + mod={mod} + prof={prof} = {total} vs DC {dc} -> "
        f"{'SUCCESS' if success else 'FAIL'}"
    )
    return success, total, d20


def opposed_check(char_a, skill_a: Skill, char_b, skill_b: Skill,
                  rng: random.Random = None) -> Tuple[bool, int, int]:
    """Opposed check between two characters. Returns (a_wins, a_total, b_total)."""
    _, a_total, _ = roll_check(char_a, skill_a, dc=0, rng=rng)
    _, b_total, _ = roll_check(char_b, skill_b, dc=0, rng=rng)
    return a_total > b_total, a_total, b_total
