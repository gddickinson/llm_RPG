# Rules Audit — how llm_RPG handles what great RPGs handle

*(2026-07-10, the baseline half of George's deep-dive: three research
agents are surveying tabletop / simulation / modern-CRPG rules; this
documents OUR current treatment of the same ten categories so the
synthesis can diff them. Updated conclusions land in
DEVELOPMENT_PLAN.md Phase 12.)*

## 1. Interacting with world & objects
- d20 + stat-modifier checks exist (`engine/skills.py`) but are used
  sparsely: persuasion/intimidation/deception, lockpicking (DEX vs
  lock level), forcing doors (STR), shove.
- Furniture layer: beds/hearths/altars/shelves/chests/anvils/wells/
  sigils/inscriptions respond to E. Objects have no HP/material yet
  (Phase 10 will add).
- **Gaps**: no general "examine/use anything" verb; no object AC/HP
  (until P10.2); no tool-quality modifiers; no group checks.

## 2. Damage & healing
- HP pools; d20 attack vs effective AC; crits (nat 20 double), fumbles;
  flanking +2; damage-type modifiers exist (silver vs troll, holy vs
  undead-ish classes).
- Healing: potions/food (heal + feed), bed rest (+30%/day), sleep at
  inns (dawn restore), well (+2), heal spells, pantheon miracle.
- Death: **failure-as-story** (robbed / left-for-dead / slain) — our
  distinctive answer to death saves; player death = popup/restart.
- **Gaps**: no damage resistance layers on armor types; no temp HP; no
  bleeding/wounds beyond the HP number; NPC healing is instant-ish.

## 3. Conditions
- Status effects: poisoned, paralyzed, blessed, cursed, frightened,
  stunned (duration ticks). Diseases (P8.2) with per-disease stat
  story. **No exhaustion ladder, no prone/grappled/restrained, no
  blinded** (FOV exists to power blinded!).

## 4. Eating / drinking / sleeping
- Hunger: player + NPC hunger ticks; starving drains HP to floor 1;
  eating heals + feeds. **No thirst.** No spoilage.
- Sleep: inns/beds; NPC fatigue exists (schedules); **player has no
  fatigue/sleep need — sleeping is purely beneficial**, never required.

## 5. Encumbrance
- NEW (Campaign 3): slot capacity 18 + 2×STR-mod, enforced at seven
  acquisition points. **No weight, no speed penalty, no push/drag.**
  Phase 11 will interact (swimming while loaded).

## 6. Skills & advancement
- Character XP levels (kills/quests) + 8-skill use-XP lattice
  (geometric curve, levels 1–50, unlock tiers in gathering) — already
  RuneScape-shaped. Diaries as achievement tiers. Guild ranks from
  quest points.
- **Gaps**: no skill ACTIONS (PF2e-style trip/demoralize); combat
  skills don't progress by use; no trainers; few perk-like unlocks
  that change verbs rather than numbers.

## 7. Trading
- Faction/relationship/diary discounts, haggle tokens (persuasion),
  merchant gold limits + restocking, director shortages,
  market indices (tâtonnement, P8.5), banking. Strong already.
- **Gaps**: no regional price differences to arbitrage BETWEEN towns
  (indices are global); no stolen-goods flagging (unseen_break_ins
  awaits a fence).

## 8. Combat
- Turn-based d20; melee/ranged+ammo/thrown; aimed shot; opportunity
  attacks + careful disengage; shove; surrounds/flanking/focus-fire
  (P7.3); targeting locks with true LOS (P8.7); durability wear.
- **Gaps**: no action economy (everything is one action per turn); no
  cover bonuses from terrain (FOV could feed it); no weapon special
  moves; no height rules; no reach differences.

## 9. Spellcasting
- Mana pools + regen; spells as data (damage/heal/status/range);
  scrolls cast, tomes teach; spell projectiles; targeting-locked
  attack spells with LOS. Pantheon miracles as divine casting.
- **Gaps**: no concentration; no AoE (P10.1 planned); no
  counterplay (dispel/counterspell); no ritual/out-of-combat casting
  identity; no environmental interactions (P10.3 fire will start).

## 10. Terrain & movement
- Swamp slows (+1 min), storms/snow slow, roads exempt; Agility
  shortcuts; water/mountain block; solid buildings + doors; rubble
  (P10) and swim/climb/fly (P11) planned.
- **Gaps**: everything in Phase 11 — plus jumping, falling damage,
  suffocation, and temperature exposure are unplanned.

## Standing strengths to preserve
Failure-as-story defeats; content-as-data with validation; the LLM
proposes / engine disposes; every system observable in the event log;
the DM charter. Any rule we adopt must keep these.
