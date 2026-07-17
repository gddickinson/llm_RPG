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
  (17). Iso parity gap remains: the social clips fall back to idle in iso.
- **I2 — Player social interactions. ✅ DONE.** The conversation quick-pick offers
  a warm gesture by your standing (`interactions.player_social_option`): a
  sweetheart may be KISSED, a friend (regard ≥ 40 / social-friend) EMBRACED, a
  friendly acquaintance's hand CLASPED; a cold/hostile NPC offers nothing.
  Choosing it (`dialog_menu` → `interactions.player_social`) plays the coordinated
  clip, warms the bond a touch more than an ambient beat, leaves the NPC a fond
  memory, and returns their reply. Tests: `tests/test_interactions.py`
  (`TestPlayerSocial`).
- **I3 — Combat grapple & throw. (more contact when fighting)** `tactics.grapple`
  (a STR-vs-STR clinch with an adjacent foe — win → the foe is GRABBED/off-guard or
  goes PRONE, both play `wrestle`) and `tactics.throw` (hurl a grabbed/adjacent foe
  — an amplified shove + `throw`/`tumble` + a hard KNOCKDOWN), plus a CONTACT beat
  on a heavy/crit melee hit (attacker follow-through + target stagger via
  `anim.interact`). Player keys + the away-agent/colosseum use them so fights read
  as physical grappling, not just swings at range.

## Constraints

- Reuse `anim.interact` + the existing clips; pure/thin; files < 500 lines.
- Heuristic-only, no per-tick LLM; cheap (nearby actors only, low per-turn chance).
- Social interactions are COSMETIC + a small relationship effect; combat grapples
  have real mechanics (contests, prone, knockback) with charter-safe caps.
- Iso: social clips currently fall back to idle — map them to existing iso gestures
  in a later polish pass (throw/thrown already read in iso).
