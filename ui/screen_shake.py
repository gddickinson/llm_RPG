"""Screen shake (GAP.5) — the missing combat JUICE.

The game had damage popups + hit flashes but no impact FEEL. This adds a
trauma-based screen shake (Eiserloh's model): events add `trauma`, the
on-screen offset scales with trauma² and decays fast, so a killing blow
or a fireball PUNCHES and settles in a third of a second. Pure +
deterministic (a fixed oscillation, no RNG) → headless-testable. Fed by
the event log; applied by blitting the map render at the offset.
"""

import math

# event keyword → trauma added (0..1). Impactful, player-relevant beats only.
TRAUMA_BY_KEYWORD = (
    ("SNEAK ATTACK", 0.6),
    ("critical hit", 0.55),
    ("Critical", 0.5),
    ("erupts", 0.6),
    ("explodes", 0.6),
    ("Fireball", 0.5),
    ("Meteor", 0.8),
    ("Earthquake", 0.8),
    ("breath", 0.6),
    ("strikes you down", 0.5),
    ("is defeated!", 0.4),
    ("hits you", 0.3),
    ("strikes you", 0.3),
    ("You are hit", 0.3),
)


class ScreenShake:
    def __init__(self, max_offset: int = 7, decay: float = 2.2):
        self.trauma = 0.0
        self.max_offset = max_offset
        self.decay = decay
        self._t = 0.0
        self.enabled = True

    def add(self, amount: float) -> None:
        if self.enabled:
            self.trauma = min(1.0, self.trauma + max(0.0, amount))

    def update(self, dt: float) -> None:
        self._t += dt
        if self.trauma > 0.0:
            self.trauma = max(0.0, self.trauma - self.decay * dt)

    @property
    def active(self) -> bool:
        return self.enabled and self.trauma > 0.02

    def offset(self):
        """Current (dx, dy) pixel offset. Deterministic given time+trauma."""
        if not self.active:
            return (0, 0)
        shake = self.trauma * self.trauma
        dx = int(self.max_offset * shake * math.sin(self._t * 41.0))
        dy = int(self.max_offset * shake * math.sin(self._t * 33.0 + 1.7))
        return (dx, dy)

    def on_event(self, text: str) -> None:
        if not text or not self.enabled:
            return
        for keyword, trauma in TRAUMA_BY_KEYWORD:
            if keyword in text:
                self.add(trauma)
                return
