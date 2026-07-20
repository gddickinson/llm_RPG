"""Away-agent action execution (split from `agent_controller` to hold the
500-line line): turns a decided plan into real player actions, temporarily
acting AS the driven character. `ctrl` is the AgentController — the plan's
source and the home of the deed log + cached goal/greeted state.
"""

from engine import agent_trade as agtrade


def execute(ctrl, engine, char, plan) -> None:
    from engine.agent_controller import acting_as

    def deed(text):
        ctrl._deed(engine, char, text)

    with acting_as(engine, char):
        k = plan[0]
        if k == "attack":
            engine.attack_character(plan[1].name)
        elif k == "shoot":
            engine.shoot_ranged(plan[1].name)
        elif k == "heal_potion":
            engine.use_item(plan[1].name)
        elif k == "drink":                    # slake thirst (M.10a)
            if plan[1] is not None:
                engine.use_item(plan[1].name)
                deed(f"drank {plan[1].name} to slake its thirst.")
            else:
                from characters.needs import drink
                drink(char)
                deed("knelt and drank from the water's edge.")
        elif k == "eat":                      # quiet hunger (M.10a)
            engine.use_item(plan[1].name)
            deed(f"ate {plan[1].name} to quiet its hunger.")
        elif k == "heal_spell":
            engine.cast_spell("heal")
        elif k == "cast":                     # attack spell (M.8c)
            engine.cast_spell(plan[1], plan[2].name)
        elif k == "loot":
            engine.pickup_item()
        elif k == "forage":                   # gather raws/food (M.8d)
            engine.forage()
        elif k == "study":                    # learn from a tome (M.8e)
            engine.use_item(plan[1].name)
        elif k == "pray":                     # a boon at a shrine (M.8e)
            engine.pray()
        elif k == "stash":                    # shelve surplus at home (M.8f)
            from engine.agent_sense import _surplus_items
            from engine import homestead as hs
            for it in _surplus_items(char):
                hs.deposit(engine, it.name)
            deed("stored its surplus in the home chest.")
        elif k == "claim_home":               # buy a derelict (M.8f)
            from engine import homestead as hs
            hs.claim(engine)
            deed("claimed a home of its own.")
        elif k == "rest":                     # camp/inn to mend (M.8a)
            try:
                from engine.rest import sleep
                sleep(engine)
                deed("made camp to mend its wounds.")
            except Exception:
                pass
        elif k == "talk":
            npc = plan[1]
            ctrl.greeted.add(npc.id)
            try:
                engine.dialog_system.player_to_npc(npc.id)
                deed(f"fell to talking with {npc.name}.")
            except Exception:
                pass
        elif k == "accept_quest":
            quest, npc = plan[1], plan[2]
            if engine.quest_manager.accept_quest(quest.id):
                deed(f"took up \"{quest.title}\" from {npc.name}.")
        elif k == "trade":                    # sell junk, buy essentials (M.8b)
            agtrade.do_trade(engine, char, plan[1], deed)
        elif k == "recruit":
            npc = plan[1]
            try:
                engine.recruit(npc.id)
                if npc.id in engine.companion_manager.party:
                    deed(f"recruited {npc.name} to the party.")
            except Exception:
                pass
        elif k == "enter_building":           # T4.1 step in for an indoor task
            from engine import agent_building as abld
            loc, task = plan[1], plan[2]
            try:
                engine.enter_building(loc)
            except Exception:
                pass
            if getattr(engine, "current_interior", None) is not None:
                abld.on_entered(ctrl, engine, loc, task)
                deed(f"stepped into the {loc.name}.")
            else:                             # a locked door turned us back
                abld.on_entry_failed(ctrl)
        elif k == "exit_building":
            try:
                engine.exit_building()
                if ctrl.goal_name:            # don't head straight back
                    ctrl.visited.add(ctrl.goal_name)
                ctrl.goal = ctrl.goal_name = None
                deed("stepped back outside.")
            except Exception:
                pass
        elif k in ("move", "flee"):
            dx, dy = plan[1]
            if dx or dy:
                engine.move_player(dx, dy)
