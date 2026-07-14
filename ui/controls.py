"""Controls reference (PUX.3) — the single source of truth for the
key-help overlay (F1 / ?).

Kept here, as data, rather than buried as a string list in
`gui.show_help` — so it can be AUDITED and unit-tested for coverage,
and so the overlay renders every control instead of clipping half of
them off the bottom of the box. `help_columns()` lays the whole
reference into two balanced columns that fit one screen.
"""

from typing import List, Tuple

# (section title, [(key, what it does), ...])
CONTROLS: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("MOVE & EXPLORE", [
        ("WASD / Arrows", "walk (edge = new region)"),
        ("Numpad 1-9", "walk 8 ways (diagonals; 5 waits)"),
        ("SHIFT + move", "RUN (near a foe: careful disengage)"),
        ("`  (backtick)", "JUMP / leap forward"),
        ("TAB", "enter / leave building or cave"),
        ("SHIFT + TAB", "force a locked door (loud)"),
        ("L", "look around"),
        ("SHIFT + L", "cycle event-log detail"),
        ("ENTER", "sleep at an inn / camp outdoors"),
    ]),
    ("FIGHT", [
        ("SPACE / F", "melee attack (worn weapon)"),
        ("R", "ranged attack (bow/sling/thrown)"),
        ("SHIFT + R", "aimed shot (+2 dmg, slower)"),
        ("[ / ]", "cycle the locked target"),
        ("SHIFT + F", "shove a foe back (STR)"),
        ("SHIFT + V", "weapon action (once per rest)"),
        ("SHIFT + T", "trip an adjacent foe"),
        ("SHIFT + I", "demoralize — Frighten a foe"),
        ("SHIFT + B", "feint — set up your next blow"),
        ("SHIFT + H", "battle medicine (field-heal)"),
        ("X", "spellbook: cast a known spell"),
        ("V", "quick-cast Heal on yourself"),
        ("H", "drink a potion"),
    ]),
    ("PEOPLE & WORLD", [
        ("T", "talk (/persuade /intimidate…)"),
        ("B", "barter with a merchant"),
        ("G / E", "pick up · use furniture · dig"),
        ("SHIFT + G", "carry a downed body"),
        ("Z", "forage herbs / harvest crops"),
        ("SHIFT + Z", "treat your pet (loyalty)"),
        ("P", "party: recruit / dismiss"),
        ("SHIFT + P", "pray at a shrine or temple"),
        ("K", "craft — browse and make"),
        ("N / M", "deposit / withdraw gold"),
        ("1 – 5", "answer a confronting guard"),
    ]),
    ("PANELS & JOURNALS", [
        ("I", "inventory + gear (equip/use/drop)"),
        ("C", "character sheet"),
        ("Q", "quest log"),
        ("O", "collection log"),
        ("J", "achievement diaries"),
        ("U", "travel menu (teleports)"),
        ("Y", "topic journal"),
    ]),
    ("SYSTEM", [
        (",", "settings & options"),
        ("F11", "toggle fullscreen"),
        ("F5 / F9", "quicksave / quickload"),
        ("F1 or ?", "this help"),
        ("ESC", "close a panel · quit map"),
    ]),
]

_KEY_W = 12


def _section_lines(section: str, entries) -> List[str]:
    lines = [section]
    for key, desc in entries:
        lines.append(f"  {key:<{_KEY_W}} {desc}")
    lines.append("")
    return lines


def help_columns() -> Tuple[List[str], List[str]]:
    """The whole reference as two balanced columns of display lines,
    split at the section boundary that most evenly divides them (so
    sections stay intact AND neither column overflows the box)."""
    blocks = [_section_lines(s, e) for s, e in CONTROLS]
    sizes = [len(b) for b in blocks]
    total = sum(sizes)
    best_k, best_diff = 1, total
    for k in range(1, len(blocks)):
        left_len = sum(sizes[:k])
        if abs(left_len - (total - left_len)) < best_diff:
            best_diff = abs(left_len - (total - left_len))
            best_k = k
    left: List[str] = sum(blocks[:best_k], [])
    right: List[str] = sum(blocks[best_k:], [])
    return left, right


def documented_keys() -> set:
    """Every key token the reference documents — for coverage tests."""
    return {key for _, entries in CONTROLS for key, _ in entries}
