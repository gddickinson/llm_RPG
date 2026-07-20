"""Magical PROTECTION by power (George): a magically-created tile or object can
only be altered by a caster AT LEAST AS POWERFUL as its creator — a hedge-wizard
can't dispel an archmage's wall of stone, nor re-forge her enchanted blade.

`WardSystem` is a sparse per-tile ward layer `{(x,y): power}` — the power of the
caster who last MAGICALLY shaped that tile. `worldcraft` stamps it on a magic
mutation and consults it before another: a weaker caster's magic is refused, and
mundane LABOUR can't touch a magic ward at all. `caster_power` is the yard-stick
(caster level + the better of the INT/WIS modifier), shared by terrain wards and
`items.enchanting` (an enchanted item carries its enchanter's power in
`metadata["ward_power"]`). Rides the save via `to_dict`/`from_dict`.
"""


def caster_power(char) -> int:
    """A caster's magical power: level + the better INT/WIS modifier. A stronger
    caster out-ranks a weaker one's wards."""
    lvl = getattr(char, "level", 1) or 1

    def mod(stat):
        return max(0, (getattr(char, stat, 10) - 10) // 2)

    return lvl + max(mod("intelligence"), mod("wisdom"))


class WardSystem:
    def __init__(self, engine):
        self.engine = engine
        self.wards = {}          # (x, y) -> power (int > 0)

    def power_at(self, x: int, y: int) -> int:
        return self.wards.get((x, y), 0)

    def set(self, x: int, y: int, power: int) -> None:
        if power and power > 0:
            self.wards[(x, y)] = int(power)
        else:
            self.wards.pop((x, y), None)

    def clear(self, x: int, y: int) -> None:
        self.wards.pop((x, y), None)

    def to_dict(self) -> dict:
        return {"wards": [[x, y, p] for (x, y), p in self.wards.items()]}

    def from_dict(self, data) -> None:
        self.wards = {(int(x), int(y)): int(p)
                      for x, y, p in (data or {}).get("wards", [])}
