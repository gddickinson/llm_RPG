"""The active pantheon (P20.4) — gods that meddle, not just watch.

The pantheon was a buff vendor: it read your deeds, granted prayer
miracles, and dropped the odd omen. The gods only ever REACTED to you.
This makes them AGENTS that reach into the world of their own accord.

Each night a god weighs how its domain fares — Solara the harvest in the
larders, Morrik the strife on the roads, Grimble the coin in the markets,
Veyra the safety of travel, the Pale Lady the reach of death — tempered by
the favor you've built with it. If its domain THRIVES (or you've honored
it), the god sends a BOON that swells its favoured faction; if its domain
is NEGLECTED, it looses WRATH. Because those faction numbers drive the
ticker's raids and the wilderness itself, a god's mood really does move the
realm. And opposing gods contend: when two who stand against each other
both act, tension climbs the heavens until it breaks in a wild-weather
storm.

Content-as-data (`data/divine_acts.json`); deterministic; the only new
state is the god-vs-god tension, which rides `player.metadata`.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.divine_acts")


class DivineActs:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    def _cfg(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("divine_acts.json")
        except Exception as e:
            logger.debug(f"divine_acts.json: {e}")
            return {}

    def _tension(self) -> int:
        return self.engine.player.metadata.get("divine_tension", 0)

    def _set_tension(self, v) -> None:
        self.engine.player.metadata["divine_tension"] = max(0, v)

    # ---- the nightly step ------------------------------------------

    def run_day(self) -> list:
        cfg = self._cfg()
        gods = cfg.get("gods", {})
        if not gods:
            return []
        ft = getattr(self.engine, "faction_ticker", None)
        if ft is None:
            return []
        favor = self.engine.player.metadata.get("god_favor", {})
        acted, beats = [], []
        for gid, spec in gods.items():
            if self.rng.random() >= cfg.get("act_chance", 0.5):
                continue
            line = self._judge(gid, spec, ft, favor, cfg)
            if line:
                beats.append(line)
                acted.append(gid)
        beats += self._contend(acted, gods, cfg)
        self._announce(beats)
        return beats

    def _judge(self, gid, spec, ft, favor, cfg):
        m = spec.get("metric", {})
        st = ft.state.get(m.get("faction"), {})
        val = st.get(m.get("stat"), 0)
        val += min(cfg.get("favor_cap", 20),
                   favor.get(gid, 0)) * cfg.get("favor_weight", 2)
        if val >= spec.get("high", 60):
            self._apply(spec.get("boon"), ft)
            return spec.get("boon_line", "")
        if val <= spec.get("low", 30):
            self._apply(spec.get("wrath"), ft)
            return spec.get("wrath_line", "")
        return None

    def _apply(self, eff, ft) -> None:
        if not eff:
            return
        st = ft.state.get(eff.get("faction"))
        stat = eff.get("stat")
        if st is not None and stat in st:
            st[stat] = max(0, min(100, st[stat] + eff.get("amount", 0)))

    def _contend(self, acted, gods, cfg):
        aset = set(acted)
        seen, clashes = set(), 0
        for gid in acted:
            opp = gods.get(gid, {}).get("opposes")
            if opp and opp in aset:
                pair = tuple(sorted((gid, opp)))
                if pair not in seen:
                    seen.add(pair)
                    clashes += 1
        if not clashes:
            return []
        tension = self._tension() + clashes
        if tension >= cfg.get("tension_at", 3):
            self._set_tension(0)
            return [cfg.get("storm_line", "The gods contend.")]
        self._set_tension(tension)
        return []

    def _announce(self, beats) -> None:
        for line in beats[:3]:
            if not line:
                continue
            self.engine.memory_manager.add_event(f"[Realm] {line}")
            try:
                self.engine.world_director.rumors.append(line)
                del self.engine.world_director.rumors[:-5]
            except Exception:
                pass
