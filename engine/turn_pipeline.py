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

    # A guard collects on the ledger (P12.9)
    try:
        self.law.check_contact()
    except Exception as e:
        logger.debug(f"Law contact error: {e}")

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
            self.world_director.run_night()
            self.faction_ticker.run_day()
            self.retaliation.run_night()
            self.disease.run_day()
            self.farm_manager.run_day()
            self.pantheon.run_day()
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

    # Advance in-flight projectiles
    try:
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

    # The world fights its own battles (P7.1)
    try:
        self.npc_conflict.update()
    except Exception as e:
        logger.debug(f"NPC conflict error: {e}")

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
