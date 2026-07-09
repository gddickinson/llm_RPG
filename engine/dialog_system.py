"""Dialog system — player↔NPC conversation through the LLM provider."""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.dialog")


class DialogSystem:
    """Player-NPC dialog with the LLM provider in the loop.

    Falls back to a hard-coded greeting if the provider yields nothing.
    """

    def __init__(self, engine):
        self.engine = engine
        self._last_player_message = None

    def player_to_npc(self, npc_id: str, message: str = None) -> str:
        npc = self.engine.npc_manager.get_npc(npc_id)
        if not npc:
            return f"NPC with ID {npc_id} not found."

        if not self._adjacent_to_player(npc):
            return f"{npc.name} is too far away to talk to."

        if not message:
            return self._greet(npc)

        # Social checks: /persuade /intimidate /deceive <argument>
        from engine.persuasion import parse_command
        cmd = parse_command(message)
        if cmd is not None:
            verb, argument = cmd
            self.engine.memory_manager.add_event(
                f"You try to {verb} {npc.name}: \"{argument}\"")
            result = self.engine.persuasion.attempt(npc, verb, argument)
            self.engine.advance_turn()
            return result

        # Player speaks ---------------------------------------------------
        self._last_player_message = message
        self.engine.memory_manager.add_event(
            f"You say to {npc.name}: \"{message}\"")

        # Structured protocol first (LLM providers), then legacy paths
        recent = self.engine.memory_manager.get_character_history(npc.name, count=5)
        response, action_note = self._via_protocol(npc, message, recent)
        if response is None:
            response = self._via_process(npc_id, message, recent) \
                or self._via_inline(npc, message, recent)

        if not response:
            response = "..."
        if action_note:
            self.engine.memory_manager.add_event(action_note)

        # Append quest offers / turn-in prompts
        response = self._append_quest_prompts(npc_id, response)

        self.engine.memory_manager.add_event(
            f"{npc.name} says: \"{response}\"")
        try:
            from engine.npc_memory import remember, log_exchange
            remember(npc, f"{self.engine.player.name} said: \"{message}\". "
                          f"I replied: \"{response}\"", 2,
                     self.engine.world.time)
            log_exchange(npc, message, response)
        except Exception:
            npc.add_memory(
                f"Player said: \"{message}\". I replied: \"{response}\"", 2)

        # Friendly conversation slowly builds trust (recruit gate is 30)
        klass = getattr(npc.character_class, "value", "")
        if klass not in ("brigand", "troll", "monster"):
            npc.modify_relationship(self.engine.player.id, 2)

        # Quest hook
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
            self.engine.quest_manager.on_npc_talked(npc_id)

        # Crossing an affinity threshold may trigger a heart event
        try:
            self.engine.heart_events.maybe_trigger(npc)
        except Exception:
            pass

        self.engine.advance_turn()
        return response

    # ---- internals ---------------------------------------------------

    def _greet(self, npc) -> str:
        recent = []
        response = self._via_process(npc.id, "Hello", recent) \
            or self._via_inline(npc, "Hello", recent)
        if not response:
            response = "Hello there, traveler."

        # Append quest offers / turn-in prompts
        response = self._append_quest_prompts(npc.id, response)

        self.engine.memory_manager.add_event(f"{npc.name} says: \"{response}\"")
        self.engine.advance_turn()
        return response

    def _append_quest_prompts(self, npc_id: str, base: str) -> str:
        qm = getattr(self.engine, "quest_manager", None)
        offered = qm.offered_by(npc_id) if qm else []
        ready = qm.ready_for_turn_in(npc_id) if qm else []

        extras = [base]
        # Known topics raised by the player get authored answers
        # (heuristic mode; LLM mode grounds them via the prompt instead)
        try:
            if getattr(self.engine.llm_interface, "provider_name",
                       "heuristic") == "heuristic" and \
                    self._last_player_message:
                npc0 = self.engine.npc_manager.get_npc(npc_id)
                if npc0 is not None:
                    for line in self.engine.topic_journal.heuristic_lines(
                            npc0, self._last_player_message):
                        extras.append(f"  {line}")
        except Exception:
            pass
        # Heuristic mode: NPCs occasionally comment on your deeds
        try:
            if getattr(self.engine.llm_interface, "provider_name",
                       "heuristic") == "heuristic":
                from engine.player_deeds import heuristic_comment
                comment = heuristic_comment(self.engine)
                if comment:
                    extras.append(f"  {comment}")
        except Exception:
            pass
        # Heuristic mode: trusted NPCs share an unlocked secret outright
        # (LLM mode reveals through the protocol action instead)
        try:
            if getattr(self.engine.llm_interface, "provider_name",
                       "heuristic") == "heuristic":
                from engine.secrets import (unlocked_secrets, reveal,
                                            locked_count)
                npc = self.engine.npc_manager.get_npc(npc_id)
                if npc is not None:
                    unlocked = unlocked_secrets(self.engine, npc)
                    if unlocked:
                        secret = unlocked[0]
                        reveal(self.engine, npc, secret["id"])
                        extras.append(
                            f"  (leaning close) {secret['text']}")
                    elif locked_count(self.engine, npc):
                        extras.append(
                            "  (They seem to be holding something back.)")
        except Exception:
            pass
        # Occasional gossip line from the NPC
        npc = self.engine.npc_manager.get_npc(npc_id)
        if npc is not None:
            try:
                from characters.gossip import gossip_for
                lines = gossip_for(npc, self.engine, max_lines=1)
                for line in lines:
                    extras.append(f"  ({line})")
            except Exception:
                pass

        for i, q in enumerate(offered, start=1):
            extras.append(f"  [Quest available] {q.title}  (press {i} to accept)")
        for j, q in enumerate(ready, start=len(offered) + 1):
            extras.append(f"  [Quest complete!] {q.title}  (press {j} to turn in)")
        return "\n".join(extras)

    def _via_protocol(self, npc, message: str, recent):
        """Structured JSON dialog (P3.1). (None, '') = not applicable."""
        try:
            from engine.dialog_protocol import run_dialog
            result = run_dialog(self.engine, npc, message, recent)
            if result is not None:
                return result
        except Exception as e:
            logger.warning(f"Dialog protocol failed: {e}")
        return (None, "")

    def _via_process(self, npc_id: str, message: str, recent) -> Optional[str]:
        pm = getattr(self.engine, "process_manager", None)
        if not pm:
            return None
        try:
            pm.send_command(npc_id, "get_dialog",
                            {"message": message, "recent_history": recent})
            resp = pm.get_response(npc_id, timeout=3.0)
            if resp and resp.get("type") == "dialog":
                return resp["response"]
        except Exception as e:
            logger.warning(f"Process-based dialog failed: {e}")
        return None

    def _via_inline(self, npc, message: str, recent) -> str:
        try:
            return self.engine.llm_interface.generate_npc_dialog(
                npc, message, recent)
        except Exception as e:
            logger.warning(f"Inline LLM dialog failed: {e}")
            return ""

    def _adjacent_to_player(self, npc) -> bool:
        px, py = self.engine.player.position
        nx, ny = npc.position
        return ((px - nx) ** 2 + (py - ny) ** 2) ** 0.5 <= 1.5
