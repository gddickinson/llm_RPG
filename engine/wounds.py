"""Body-part wounds (P15.9) — where you're hurt matters.

Layered UNDER the HP/dying model, not replacing it: HP is still the
life bar, but a serious hit also WOUNDS a body part, and where the
wound lands shapes what you can do:

- HEAD   — every d20 check suffers (−severity)
- ARMS   — your attacks suffer (−severity to hit)
- LEGS   — every step drags (+severity minutes)
- TORSO  — your effective HP ceiling drops (−15% per severity)

Each part carries a severity 0–3 (sound / bruised / wounded /
crippled). A hit for WOUND_THRESHOLD+ rolls one random part up a
step (torso is likeliest — it's the biggest target). A crippled
limb also festers: it raises the P12.12 infection chance. Wounds
knit slowly — one severity per part per real night's sleep, or
faster with Battle Medicine (P12.8) tending a limb. State lives on
player.metadata, so it rides save/load for free.
"""

import logging

logger = logging.getLogger("llm_rpg.wounds")

PARTS = ("head", "torso", "left_arm", "right_arm", "legs")
# torso doubled — the broad side of the barn
WOUND_TABLE = ("head", "torso", "torso", "left_arm",
               "right_arm", "legs")
SEVERITY_MAX = 3
WOUND_THRESHOLD = 6       # damage that can crack a bone
TORSO_HP_STEP = 0.15      # effective-HP ceiling lost per torso rung
SEVERITY_WORD = ("sound", "bruised", "wounded", "crippled")


def wounds(player) -> dict:
    return player.metadata.setdefault("wounds", {})


def severity(player, part: str) -> int:
    return int(wounds(player).get(part, 0))


def total(player) -> int:
    return sum(wounds(player).values())


def _arm_severity(player) -> int:
    """The better of two arms swings — the worse arm doesn't stop
    you, it just doesn't help."""
    return min(severity(player, "left_arm"),
               severity(player, "right_arm"))


def wound_part(engine, part: str = None, rng=None) -> str:
    """Crack a body part up one severity. Returns a log line (or ''
    if already crippled)."""
    player = engine.player
    rng = rng or engine.combat_system.rng
    if part is None:
        part = WOUND_TABLE[rng.randint(0, len(WOUND_TABLE) - 1)]
    w = wounds(player)
    cur = w.get(part, 0)
    if cur >= SEVERITY_MAX:
        return ""
    w[part] = cur + 1
    label = part.replace("_", " ")
    word = SEVERITY_WORD[w[part]]
    msg = f"[!] Your {label} is {word}!"
    engine.memory_manager.add_event(msg)
    if w[part] >= SEVERITY_MAX:
        try:   # a shattered limb festers (P12.12)
            from engine.infection import maybe_infect
            maybe_infect(engine, 0.35, f"the crippled {label}")
        except Exception:
            pass
    return msg


def maybe_wound(engine, damage: int, victim) -> None:
    """A serious hit to the PLAYER may break something."""
    if victim.id != engine.player.id or damage < WOUND_THRESHOLD:
        return
    # chance scales with how hard the blow landed
    chance = min(0.6, 0.15 + 0.03 * (damage - WOUND_THRESHOLD))
    if engine.combat_system.rng.random() < chance:
        wound_part(engine)


# ---- the penalties (same shape as conditions/exhaustion) --------

def check_penalty(player) -> int:
    return -severity(player, "head")


def attack_penalty(player) -> int:
    return -_arm_severity(player)


def step_minutes(player) -> int:
    return severity(player, "legs")


def hp_ceiling(player) -> int:
    """Effective max HP after torso wounds (min 1)."""
    frac = 1.0 - TORSO_HP_STEP * severity(player, "torso")
    return max(1, int(player.max_hp * frac))


def apply_hp_ceiling(player) -> None:
    # only a torso wound lowers the ceiling — a sound torso must
    # never clamp legitimate overheals (the Hearty Brew, P12.5)
    if severity(player, "torso") <= 0:
        return
    cap = hp_ceiling(player)
    if player.hp > cap:
        player.hp = cap


# ---- healing ----------------------------------------------------

def heal_wounds(player, amount: int = 1) -> int:
    """Knit the worst wound(s) down by `amount` severity total."""
    w = wounds(player)
    healed = 0
    while healed < amount:
        part = max((p for p in w if w[p] > 0),
                   key=lambda p: w[p], default=None)
        if part is None:
            break
        w[part] -= 1
        if w[part] <= 0:
            del w[part]
        healed += 1
    return healed


def tend_limb(engine) -> str:
    """Battle Medicine's wound-tending: mend the worst limb by one."""
    player = engine.player
    if total(player) <= 0:
        return ""
    before = max((p for p in wounds(player)
                  if wounds(player)[p] > 0),
                 key=lambda p: wounds(player)[p], default=None)
    heal_wounds(player, 1)
    if before:
        return f" You also set the {before.replace('_', ' ')}."
    return ""


def status_line(player) -> str:
    """The hint/HUD summary of what's broken."""
    hurt = [f"{p.replace('_', ' ')} ({SEVERITY_WORD[s]})"
            for p, s in wounds(player).items() if s > 0]
    if not hurt:
        return ""
    return "[!] wounds: " + ", ".join(hurt)
