"""Battle package (Phase 17) — the large-scale tactical layer.

P17.1 ships the data-driven, headless FOUNDATION: the army/unit
tables (data/battles/*.json) and a deterministic Lanchester
`resolve()` auto-resolver. No UI, no per-tick loop — a seeded
function that takes two armies and returns a result. It doubles as
the richer off-screen battle resolver for the faction systems.

Later rounds add the grid squad model, group AI, the zoomable
screen, orders, siege, and player role-swap (P17.2–P17.8).
"""

from engine.battle.battle_resolve import (Army, resolve,  # noqa: F401
                                          unit_category)
