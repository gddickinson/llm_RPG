"""D&D-style skill system with PF2e degrees of success (P12.1).

Skills map to an ability score (STR/DEX/CON/INT/WIS/CHA). A check is
1d20 + ability modifier vs a difficulty class (DC), graded into FOUR
outcomes: beat the DC by 10+ = critical success, miss by 10+ =
critical failure, and a natural 20/1 shifts the result one degree.
Every system that rolls (lockpicking, persuasion, forcing doors,
shove, forage) routes through `check()` so jackpots and fumbles
exist everywhere.
"""

import logging
import random
from dataclasses import dataclass
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


class Degree(Enum):
    """PF2e's four degrees of success."""
    CRIT_FAIL = 0
    FAIL = 1
    SUCCESS = 2
    CRIT_SUCCESS = 3


@dataclass
class CheckResult:
    degree: Degree
    total: int
    d20: int
    dc: int

    @property
    def success(self) -> bool:
        return self.degree in (Degree.SUCCESS, Degree.CRIT_SUCCESS)

    @property
    def crit(self) -> bool:
        return self.degree in (Degree.CRIT_FAIL, Degree.CRIT_SUCCESS)


def degree_of(total: int, dc: int, d20: int) -> Degree:
    """Grade a roll: +/-10 margins crit; nat 20/1 shift one degree."""
    if total >= dc + 10:
        deg = Degree.CRIT_SUCCESS
    elif total >= dc:
        deg = Degree.SUCCESS
    elif total <= dc - 10:
        deg = Degree.CRIT_FAIL
    else:
        deg = Degree.FAIL
    if d20 == 20:
        deg = Degree(min(deg.value + 1, 3))
    elif d20 == 1:
        deg = Degree(max(deg.value - 1, 0))
    return deg


def check(character, skill: Skill, dc: int = 10,
          proficient: bool = False, advantage: bool = False,
          disadvantage: bool = False,
          rng: random.Random = None) -> CheckResult:
    """The graded check core: everything that rolls comes here."""
    ok, total, d20 = roll_check(character, skill, dc,
                                proficient, advantage,
                                disadvantage, rng)
    return CheckResult(degree_of(total, dc, d20), total, d20, dc)


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
