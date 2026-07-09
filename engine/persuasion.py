"""Social checks with stakes — persuade / intimidate / deceive (P3.4).

The Suck Up! pattern: one clear verb, one binary outcome, the LLM as
judge. In dialog, the player types `/persuade <argument>` (or
/intimidate, /deceive). Adjudication:

- LLM mode: the model judges the ARGUMENT against the NPC's personality,
  relationship, and the player's relevant stat, returning
  {"success": bool, "reason": "..."} (defensively parsed; junk = fail).
- Heuristic mode: d20 + stat modifier + relationship/10 vs DC 14.

Stakes (why it's not chat): failure costs -6 affinity AND locks that
verb with that NPC for a full game-day — no retry spam. Success pays
out mechanically: persuading a merchant earns a 20%-off haggle token,
intimidation frightens the target (real combat debuff), deception
builds (false) trust.
"""

import json
import logging
import random
import re
from typing import Dict, Optional, Tuple

logger = logging.getLogger("llm_rpg.persuasion")

VERBS = {
    "persuade": "charisma",
    "intimidate": "strength",
    "deceive": "intelligence",
}
DC = 14
LOCKOUT_MINUTES = 24 * 60
HAGGLE_MINUTES = 24 * 60
FAIL_AFFINITY = -6

JUDGE_SYSTEM = """You judge a social attempt in a fantasy RPG. Given the NPC's personality and the player's argument, decide if it works ON THIS NPC.
Be strict: weak, generic, or insulting arguments fail. A relevant, in-character argument that plays to the NPC's traits, likes, or interests succeeds.
Reply with ONLY JSON: {"success": true/false, "reason": "<one short sentence>"}"""


def parse_command(message: str) -> Optional[Tuple[str, str]]:
    """'/persuade give me a discount' -> ('persuade', 'give me a discount')."""
    m = re.match(r"^/(persuade|intimidate|deceive)\s+(.+)$",
                 message.strip(), re.IGNORECASE)
    if not m:
        return None
    return (m.group(1).lower(), m.group(2).strip())


class PersuasionSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    # ---- lockout ---------------------------------------------------------

    def _locks(self) -> Dict[str, int]:
        return self.engine.player.metadata.setdefault(
            "persuasion_locks", {})

    def locked_until(self, npc, verb: str) -> int:
        return self._locks().get(f"{npc.id}:{verb}", 0)

    def is_locked(self, npc, verb: str) -> bool:
        return self.engine.world.time < self.locked_until(npc, verb)

    # ---- adjudication -------------------------------------------------------

    def attempt(self, npc, verb: str, argument: str) -> str:
        if verb not in VERBS:
            return "You can /persuade, /intimidate, or /deceive."
        if self.is_locked(npc, verb):
            return (f"{npc.name} is in no mood for that again today. "
                    f"(Try something else, or come back tomorrow.)")

        success, reason = self._judge(npc, verb, argument)
        if success:
            note = self._apply_success(npc, verb)
            msg = (f"[{verb.title()} SUCCESS] {reason} {note}").strip()
        else:
            npc.modify_relationship(self.engine.player.id, FAIL_AFFINITY)
            self._locks()[f"{npc.id}:{verb}"] = \
                self.engine.world.time + LOCKOUT_MINUTES
            msg = (f"[{verb.title()} FAILED] {reason} "
                   f"({npc.name} is annoyed — that approach is spent "
                   f"for today.)")
        self.engine.memory_manager.add_event(msg)
        from engine.npc_memory import remember
        remember(npc, f"{self.engine.player.name} tried to {verb} me "
                      f"and {'succeeded' if success else 'failed'}.",
                 4, self.engine.world.time)
        return msg

    def _judge(self, npc, verb: str, argument: str) -> Tuple[bool, str]:
        iface = getattr(self.engine, "llm_interface", None)
        if iface is not None and getattr(iface, "provider_name",
                                         "heuristic") != "heuristic":
            verdict = self._llm_judge(npc, verb, argument)
            if verdict is not None:
                return verdict
        return self._dice_judge(npc, verb)

    def _llm_judge(self, npc, verb, argument) -> Optional[Tuple[bool, str]]:
        player = self.engine.player
        stat = VERBS[verb]
        mod = player.get_stat_modifier(stat)
        rel = npc.get_relationship(player.id)
        traits = ", ".join(npc.personality.get("traits", []))
        prompt = (
            f"NPC: {npc.name}, a {npc.character_class.value}. "
            f"Traits: {traits}. Likes: "
            f"{npc.personality.get('likes', [])}. "
            f"Feelings toward the player: {rel} (-100..100).\n"
            f"The player attempts to {verb.upper()} them. The player's "
            f"{stat} modifier is {mod:+d} (favor success when high, "
            f"doubt it when negative).\n"
            f"Player's argument: \"{argument}\"\n\nJudge it.")
        try:
            raw = self.engine.llm_interface.generate_response(
                prompt, JUDGE_SYSTEM, max_tokens=120, temperature=0.4)
            m = re.search(r"\{.*\}", raw or "", re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(0))
            return (bool(data.get("success")),
                    str(data.get("reason", ""))[:200])
        except Exception as e:
            logger.debug(f"LLM judge failed: {e}")
            return None

    def _dice_judge(self, npc, verb) -> Tuple[bool, str]:
        player = self.engine.player
        stat = VERBS[verb]
        mod = player.get_stat_modifier(stat)
        rel_bonus = npc.get_relationship(player.id) // 10
        roll = self.rng.randint(1, 20)
        total = roll + mod + rel_bonus
        success = total >= DC
        return (success,
                f"(d20 {roll} {mod:+d} {stat[:3].upper()} "
                f"{rel_bonus:+d} rapport = {total} vs DC {DC})")

    # ---- consequences --------------------------------------------------------

    def _apply_success(self, npc, verb: str) -> str:
        player = self.engine.player
        if verb == "persuade":
            npc.modify_relationship(player.id, 8)
            klass = getattr(npc.character_class, "value", "")
            if klass in ("merchant", "cleric", "wizard", "ranger"):
                haggles = player.metadata.setdefault("haggle", {})
                haggles[npc.id] = self.engine.world.time + HAGGLE_MINUTES
                return f"{npc.name} agrees to better prices today!"
            return f"{npc.name} comes around to your view."
        if verb == "intimidate":
            from characters.status_effects import apply_effect
            apply_effect(npc, "frightened", duration=8)
            npc.modify_relationship(player.id, -2)
            return f"{npc.name} backs down, shaken."
        if verb == "deceive":
            npc.modify_relationship(player.id, 5)
            return f"{npc.name} believes you."
        return ""

    def haggle_active(self, npc) -> bool:
        expiry = self.engine.player.metadata.get("haggle", {}) \
            .get(npc.id, 0)
        return self.engine.world.time < expiry
