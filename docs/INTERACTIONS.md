# INTERACTIONS.md — richer character-to-character interactions

George: "create ways for characters to better interact — wrestling, hugging,
throwing each other, more contact when fighting, shaking hands, kissing, etc."
Build in tested rounds on `v2-development`; render/verify; keep the suite green;
commit each round.

## What already exists (the foundation)

- **`engine/anim.interact(a, b, kind)`** — the two-character INTERACTION primitive:
  each side faces the other and plays its half of a coordinated clip. Kinds:
  `handshake`, `hug`, `kiss`, `wrestle`, `throw` (a throws / b tumbles),
  `knockdown` (a strikes / b falls), `guard`.
- **Clips** — `char_clips` ships all the halves (handshake/hug/kiss/wrestle/throw/
  tumble/knockdown). 2D plays them (procedural). Iso has baked `throw`/`thrown`
  only — the social clips fall back to idle in iso (a parity gap; map later).
- **`anim.update_idle_life(engine)`** — the per-turn ambient-life hook (fidgets +
  startle). The natural home for AMBIENT social interactions.
- **Combat** — attacks (COMBAT.1/2 swings + hit reactions); `tactics.shove` already
  ends a crit with `anim.interact(player, target, "knockdown")`.
- **Relationships** — `char.get_relationship(id)` / `relationships`; the social
  graph (FRIEND/FEUD, `metadata["social"]`); romance couples (`metadata["romance"]`,
  a `partner`); families; factions.

The primitive is there — what's MISSING is TRIGGERING it in gameplay + real combat
grapples. That's this feature.

## Rounds

- **I1 — Ambient social interactions. ✅ DONE.** `engine/interactions.py` — for two
  ADJACENT idle non-hostiles, `social_kind` picks the interaction by their standing
  (a romance PARTNER → KISS, warm friends / social FRIEND → HUG, friendly
  acquaintances → HANDSHAKE, a FEUD / cold-regard pair → SQUARE UP) and
  `perform_social` plays it via `anim.interact` with a small mutual regard nudge +
  a sparse near-player `[Town]` beat. `update_social` is the per-turn ambient pass
  (deduped, `_COOLDOWN`=24 turns, low chance), wired into `turn_pipeline` after
  `update_idle_life`. The social graph is now VISIBLE — friends embrace, couples
  kiss, rivals bristle. Weapon fix: a hand-busy social clip (`_EMPTY_HANDED` in
  `body_renderer`) draws NO weapon/shield, so a hug/kiss/handshake doesn't read as
  a raised sword (a square-up keeps its weapon). Tests: `tests/test_interactions.py`
  (17).
- **I4 — Iso parity. ✅ DONE.** The two-character interaction clips are now in the
  iso `_CLIP` map (`iso_skeleton`) → nearest baked mocap (handshake/hug→beckon,
  kiss→nod, wrestle→charge, tumble→thrown, knockdown→stagger, taunt→argue) instead
  of freezing to idle; and `iso_chars.kit_of` drops the weapon/shield during a
  hand-busy social clip in iso too (parity with `_EMPTY_HANDED`). There's no true
  hug/kiss mocap, so iso reads the intent approximately — but the figures play a
  fitting gesture and face each other, unarmed for an embrace. Tests:
  `test_iso_chars.TestInteractionParity`.
- **I2 — Player social interactions. ✅ DONE.** The conversation quick-pick offers
  a warm gesture by your standing (`interactions.player_social_option`): a
  sweetheart may be KISSED, a friend (regard ≥ 40 / social-friend) EMBRACED, a
  friendly acquaintance's hand CLASPED; a cold/hostile NPC offers nothing.
  Choosing it (`dialog_menu` → `interactions.player_social`) plays the coordinated
  clip, warms the bond a touch more than an ambient beat, leaves the NPC a fond
  memory, and returns their reply. Tests: `tests/test_interactions.py`
  (`TestPlayerSocial`).
- **I3 — Combat grapple & throw. ✅ DONE.** `tactics.grapple` (a STR-vs-(STR|DEX)
  clinch with the nearest adjacent foe — both play `wrestle`; win → the foe is
  GRABBED/off-guard, a firm win PINS it prone; a bad loss throws the player off
  balance) and `tactics.throw` (hurl a grabbed/adjacent foe — an amplified shove
  up to 2 tiles + `throw`/`tumble` + a hard PRONE knockdown + fall damage; a
  grabbed foe is far easier to throw). `is_grappling` tracks the clinch. One key:
  **SHIFT+C** clinches, then throws while clinched (`input_actions.grapple_verb`);
  documented in `controls`, advertised state-aware in the combat `hints`. Tests:
  `test_tactics.TestGrappleThrow`. So you can now wrestle a foe down and hurl it —
  physical contact mid-fight, not just swings at range.

- **I5 — Combat contact for the whole world. ✅ DONE.** A decisive melee CRIT (in
  `combat_system._resolve`) that fells or nearly fells a non-player foe now drives
  it to the ground — `anim.interact(attacker, defender, "knockdown")`: the attacker
  follows through, the struck body FALLS. This fires for the player's kills AND for
  NPC-vs-NPC clashes (the same resolver runs both), so fights everywhere read as
  physical, not just swings at range. Cosmetic (emotes only), tightly gated to a
  crit + a low/dead non-player defender so it always reads as a real beatdown.
  Tests: `test_combat.TestCombatContact`.

## Constraints

- Reuse `anim.interact` + the existing clips; pure/thin; files < 500 lines.
- Heuristic-only, no per-tick LLM; cheap (nearby actors only, low per-turn chance).
- Social interactions are COSMETIC + a small relationship effect; combat grapples
  have real mechanics (contests, prone, knockback) with charter-safe caps.
- Iso: the interaction clips now map to nearest baked gestures (I4) — approximate
  (no true hug/kiss mocap) but no longer a frozen idle; weapon suppressed for a
  social clip. A bespoke procedural embrace/kiss pose could sharpen it later.
