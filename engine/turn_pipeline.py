"""The turn pipeline (split from game_engine, P14.1).

`run_turn(engine)` is everything that happens when one game minute
passes: quests tick, needs grow, encounters roll, companions and
conflicts move, surfaces burn, floods spread, hazards bite, the
dying struggle, the law collects, pets fetch — and on a day
boundary the whole nightly stack fires. game_engine.advance_turn
delegates here; the order of these blocks is load-bearing.
"""

import logging

import config

logger = logging.getLogger("llm_rpg.turns")


def run_turn(engine) -> None:
    self = engine   # body moved verbatim from advance_turn
    self.turn_counter += 1
    self.world.advance_time(1)
    if self.quest_manager:
        self.quest_manager.on_turn_advanced()

    # Tick NPC needs (game minutes pass)
    try:
        from characters.needs import tick_needs
        for npc in self.npc_manager.npcs.values():
            if npc.is_active():
                tick_needs(npc, elapsed_minutes=1)
    except Exception as e:
        logger.debug(f"Needs tick error: {e}")

    # Player needs: hunger/thirst/tiredness growth, drains,
    # the exhaustion ladder and its collapse (P12.3)
    try:
        from characters.needs import player_needs_turn
        player_needs_turn(self)
    except Exception as e:
        logger.debug(f"Player needs tick error: {e}")

    # Down at 0 HP: the recovery check (P12.4)
    try:
        from engine.dying import dying_tick
        dying_tick(self)
    except Exception as e:
        logger.debug(f"Dying tick error: {e}")

    # Back on the spot you fell? Reclaim your bloodstain (soulslike)
    try:
        from engine.checkpoint import tick as checkpoint_tick
        checkpoint_tick(self)
    except Exception as e:
        logger.debug(f"Checkpoint tick error: {e}")

    # A lair whose last defender has fallen yields its hoard (P19.2)
    try:
        self.lairs.check_cleared()
    except Exception as e:
        logger.debug(f"Lair clear-check error: {e}")

    # The main arc's finale — the age is won (P21.2)
    try:
        from engine.campaign import check_finale
        check_finale(self)
    except Exception as e:
        logger.debug(f"Campaign finale error: {e}")

    # A guard collects on the ledger (P12.9)
    try:
        self.law.check_contact()
    except Exception as e:
        logger.debug(f"Law contact error: {e}")

    # The road talks (P15.5)
    try:
        self.companion_manager.banter_tick()
    except Exception as e:
        logger.debug(f"Banter error: {e}")

    # A loyal pet may fetch (P12.14)
    try:
        self.pet_system.maybe_fetch()
    except Exception as e:
        logger.debug(f"Pet fetch error: {e}")

    # Tick status effects on all active characters (player + NPCs)
    try:
        from characters.status_effects import tick_effects
        for char in [self.player] + list(self.npc_manager.npcs.values()):
            if char and char.is_active():
                events = tick_effects(char, self)
                for ev in events:
                    self.memory_manager.add_event(ev)
    except Exception as e:
        logger.debug(f"Status effects tick error: {e}")

    # Slow mana regen for the player (1/turn while not in combat — simplified)
    try:
        from engine.spells import rest_recover_mana, ensure_mana
        ensure_mana(self.player)
        if self.turn_counter % 5 == 0:
            rest_recover_mana(self.player, amount=1)
    except Exception as e:
        logger.debug(f"Mana regen error: {e}")

    # P27.2 slow passive HP recovery between fights — a wound knits on its
    # own when safe & provided for, so chronic low HP isn't the default state
    try:
        from engine.regen import tick_hp_regen
        tick_hp_regen(self)
    except Exception as e:
        logger.debug(f"HP regen error: {e}")

    # Random wilderness encounter
    try:
        msg = self.encounter_manager.maybe_spawn()
        if msg:
            self.memory_manager.add_event(msg)
    except Exception as e:
        logger.debug(f"Encounter spawn error: {e}")

    # Weather changes
    try:
        wmsg = self.weather_system.tick()
        if wmsg:
            self.memory_manager.add_event(wmsg)
    except Exception as e:
        logger.debug(f"Weather tick error: {e}")

    # Shops restock daily (checked every 30 turns; cheap)
    try:
        if self.turn_counter % 30 == 0:
            self.shop_manager.refresh_all_if_due()
    except Exception as e:
        logger.debug(f"Shop restock error: {e}")

    # Collection log scan (items in bag + current place)
    try:
        self.collection_log.tick()
    except Exception as e:
        logger.debug(f"Collection tick error: {e}")

    # Pet follower trails the player
    try:
        self.pet_system.update()
    except Exception as e:
        logger.debug(f"Pet update error: {e}")

    # Diary tiers auto-claim when their tasks are all done
    try:
        if self.turn_counter % 10 == 0:
            self.diary_manager.check_and_claim()
    except Exception as e:
        logger.debug(f"Diary check error: {e}")

    # Nightly: NPC reflection + the world director's overnight events
    try:
        day = self.world.time // (24 * 60)
        if day != getattr(self, "_last_reflection_day", day):
            from engine.npc_memory import nightly_reflection
            nightly_reflection(self)
            try:   # a night without a bed is sleep debt (P12.3)
                from characters.needs import run_player_night
                run_player_night(self, day - 1)
            except Exception as e:
                logger.debug(f"Sleep debt error: {e}")
            try:   # the beaten come to (P12.4)
                from engine.dying import wake_the_fallen
                wake_the_fallen(self)
            except Exception as e:
                logger.debug(f"KO wake error: {e}")
            try:   # rations age in the pack (P12.5)
                from engine.food import decay_inventory
                decay_inventory(self)
            except Exception as e:
                logger.debug(f"Food decay error: {e}")
            try:   # the infection race advances (P12.12)
                from engine.infection import infection_night
                infection_night(self)
            except Exception as e:
                logger.debug(f"Infection error: {e}")
            try:   # neglected pets drift (P12.14)
                self.pet_system.run_night()
            except Exception as e:
                logger.debug(f"Pet night error: {e}")
            try:   # a neglected mount bolts (P28.2c)
                from engine.mounts import run_night as mount_night
                mount_night(self)
            except Exception as e:
                logger.debug(f"Mount night error: {e}")
            self.world_director.run_night()
            try:   # NPCs pursue their private ambitions (P20.1)
                self.ambitions.run_day()
            except Exception as e:
                logger.debug(f"Ambitions error: {e}")
            try:   # the peer social graph drifts — friends & feuds (P20.2)
                self.social_graph.run_day()
            except Exception as e:
                logger.debug(f"Social graph error: {e}")
            try:   # a spouse provides; grudges harden into rivalry (P20.6)
                self.romance.run_day()
            except Exception as e:
                logger.debug(f"Romance error: {e}")
            try:   # paid party members draw their wage — or walk (M.7)
                self.hirelings.run_day(day)
            except Exception as e:
                logger.debug(f"Hireling upkeep error: {e}")
            self.faction_ticker.run_day()
            try:   # factions pursue agendas & diplomacy after the day's clash (P20.3)
                self.faction_agendas.run_day()
            except Exception as e:
                logger.debug(f"Faction agendas error: {e}")
            try:   # wild tribes grow and raid the settlements (P19.4)
                self.monster_tribes.run_day()
            except Exception as e:
                logger.debug(f"Monster tribes error: {e}")
            try:   # wildlife herds breed and starve overnight (P32.4b)
                self.wildlife.run_day()
            except Exception as e:
                logger.debug(f"Wildlife day error: {e}")
            try:   # a nemesis may return to hunt the player (P19.6)
                self.nemesis.run_day()
            except Exception as e:
                logger.debug(f"Nemesis error: {e}")
            try:   # a war-host may march on the castle (P17.8d)
                from engine.castle_siege_event import maybe_besiege
                maybe_besiege(self, self.faction_ticker.rng)
            except Exception as e:
                logger.debug(f"Castle siege event error: {e}")
            try:   # villages make goods overnight (P16.2)
                self.production.run_day()
            except Exception as e:
                logger.debug(f"Production loop error: {e}")
            try:   # logged-out groves regrow (P16.4)
                self.resource_nodes.run_day()
            except Exception as e:
                logger.debug(f"Resource regrowth error: {e}")
            self.retaliation.run_night()
            self.disease.run_day()
            self.farm_manager.run_day()
            self.pantheon.run_day()
            try:   # the gods reach into the world of their own accord (P20.4)
                self.divine_acts.run_day()
            except Exception as e:
                logger.debug(f"Divine acts error: {e}")
            self.market.run_day()
            self.door_manager.run_day()
            try:
                from engine.giants import run_night_labor
                run_night_labor(self)
            except Exception as e:
                logger.debug(f"Night labor error: {e}")
            try:
                from world.astronomy import announce_conjunction
                announce_conjunction(self, day)
            except Exception:
                pass
            self.radiant_quests.run_morning()
            self.dm.run_scheduled()
            try:
                self.dm_autonomous.run_day()
            except Exception as e:
                logger.debug(f"Autonomous DM error: {e}")
            if self.dm_bridge is not None:
                self.dm_bridge.export_digest()
            from engine.rest import snapshot
            self._day_metrics = snapshot(self)
        self._last_reflection_day = day
    except Exception as e:
        logger.debug(f"Nightly systems error: {e}")

    # Advance in-flight projectiles. When a GUI is animating them frame-by-frame
    # (`animate_projectiles`), it ticks + resolves them so the ARROW IS SEEN in
    # flight (George); here we only resolve them in the headless / turn-based
    # path so a shot still lands without a renderer.
    try:
        if not getattr(self, "animate_projectiles", False):
            results = self.projectile_manager.tick(dt=1.0)
            for r in results:
                if r.message:
                    self.memory_manager.add_event(r.message)
    except Exception as e:
        logger.debug(f"Projectile tick error: {e}")

    # Companions follow / fight
    try:
        self.companion_manager.update()
    except Exception as e:
        logger.debug(f"Companion update error: {e}")

    # Agent-driven heroes take their turn through the real action API
    # (M.2). advance_turn is re-entrancy-guarded, so their moves don't
    # cascade another world tick.
    try:
        from engine.agent_controller import drive_agents
        drive_agents(self)
    except Exception as e:
        logger.debug(f"Agent drive error: {e}")

    # The world's OTHER heroes live their own adventuring lives (P-M.6)
    try:
        self.adventurers.run_turn()
    except Exception as e:
        logger.debug(f"Adventurer drive error: {e}")

    # The world fights its own battles (P7.1)
    try:
        self.npc_conflict.update()
    except Exception as e:
        logger.debug(f"NPC conflict error: {e}")

    # Faster creatures run the hero down — every turn, not the AI cadence
    # (P32.1). A wolf closes; a shambler falls behind; a mount outruns both.
    try:
        self.pursuit.update()
    except Exception as e:
        logger.debug(f"Pursuit error: {e}")

    # P37.6b: an adjacent hostile PRESSES the attack every turn (not the 5-turn
    # AI cadence), so monsters no longer just stand and get killed
    try:
        self.aggression.update()
    except Exception as e:
        logger.debug(f"Aggression error: {e}")

    # the COLOSSEUM drives a staged fight every tick (combat-testing arena)
    try:
        if getattr(self, "colosseum", None) and self.colosseum.active:
            self.colosseum.run_turn()
    except Exception as e:
        logger.debug(f"Colosseum error: {e}")

    # Neutral wildlife graze, wander and flee (P32.3) — the living wild
    try:
        self.wildlife.update()
    except Exception as e:
        logger.debug(f"Wildlife error: {e}")

    # M2b: a nearby caster NPC / away-hero occasionally reshapes the wilderness
    try:
        from engine import ambient_magic
        ambient_magic.run(self)
    except Exception as e:
        logger.debug(f"Ambient magic error: {e}")

    # Tower guards loose arrows at attackers at the walls (P31.1c)
    try:
        self.tower_defense.update()
    except Exception as e:
        logger.debug(f"Tower defense error: {e}")

    # Town gates close by night, lock under alarm, open by day (P31.1d)
    try:
        self.town_gates.sync()
    except Exception as e:
        logger.debug(f"Town gates error: {e}")

    # Reveal what the player can see; fog the rest (P15.11)
    try:
        from engine.discovery import update as _discovery_update
        _discovery_update(self)
    except Exception as e:
        logger.debug(f"Discovery error: {e}")

    # The hero swims across deep water (P33.6c); the cast glances about (P34.3)
    # and lives an ambient idle life — fidgets, startles at threats (P34.4)
    try:
        from engine import anim
        anim.update_swim(self)
        anim.update_look(self)
        anim.update_idle_life(self)
        anim.update_fx(self)
    except Exception as e:
        logger.debug(f"Anim state error: {e}")

    # I1 — the cast SHARES social interactions: two adjacent friendly (or
    # feuding) neighbours embrace / shake hands / kiss / square up, so the
    # social graph becomes visible in the world
    try:
        from engine import interactions
        interactions.update_social(self)
    except Exception as e:
        logger.debug(f"Social interaction error: {e}")

    # Catch your breath — sprint stamina recovers each turn you're not sprinting
    try:
        from engine import stamina
        stamina.recover(self.player)
    except Exception as e:
        logger.debug(f"Stamina regen error: {e}")

    # Keep the ranged lock honest (P8.7 UX)
    try:
        self.targeting.refresh()
    except Exception as e:
        logger.debug(f"Targeting refresh error: {e}")

    # Fires burn, spread, and gutter (P10.3)
    try:
        self.surfaces_layer.tick()
    except Exception as e:
        logger.debug(f"Surface tick error: {e}")

    # Floods spread and recede (P10.6)
    try:
        self.flood_system.tick()
    except Exception as e:
        logger.debug(f"Flood tick error: {e}")

    # Deep water makes you struggle (P11.2)
    try:
        from engine.hazards import water_hazard_tick
        water_hazard_tick(self)
    except Exception as e:
        logger.debug(f"Hazard tick error: {e}")

    if self.turn_counter % config.NPC_ACTION_INTERVAL == 0:
        self.process_npc_turns_async()
