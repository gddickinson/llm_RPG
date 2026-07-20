"""Adaptive procedural MUSIC (the score layer over `ui/music_synth.py`).

A `MusicManager` renders each mood (data/music.json) to a loopable
Sound on first use, then crossfades between moods as the game state
changes — a calm road theme gives way to a pulse of tension as a
hostile nears, to a driving combat bed when blades cross, to a sparse
night motif after dark. Mood SELECTION (`select_mood`) is pure and
unit-tested; playback degrades silently without a mixer (headless/CI).

Gated by the "music" player setting.
"""

import json
import logging
import os

try:
    import numpy as np
    import pygame
    AUDIO_OK = True
except ImportError:                       # pragma: no cover
    AUDIO_OK = False

from ui import music_synth

logger = logging.getLogger("llm_rpg.music")

MUSIC_MASTER = 0.5                        # music sits UNDER the SFX
FADE_DUR = 2.2                            # crossfade seconds
REEVAL_EVERY = 0.75                       # seconds between mood re-checks
_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "music.json")


def select_mood(*, in_combat, threat_dist, in_dungeon, in_town,
                is_night) -> str:
    """Pure mood policy — the adaptive brain. Highest urgency wins."""
    if in_combat:
        return "combat"
    if threat_dist is not None and threat_dist <= 6:
        return "tension"
    if in_dungeon:
        return "dungeon"
    if in_town:
        return "town"
    if is_night:
        return "night"
    return "explore"


def read_state(engine) -> dict:
    """Extract the (cheap) state `select_mood` needs from the engine."""
    player = engine.player
    px, py = player.position
    z = getattr(engine, "current_interior", None) \
        or getattr(engine, "current_dungeon", None)
    zone_name = getattr(z, "name", None) if z else None
    in_dungeon = bool(getattr(engine, "current_dungeon", None))
    in_interior = bool(getattr(engine, "current_interior", None))

    best = None
    try:
        from engine.agent_sense import _is_hostile, _colocated
        for npc in engine.npc_manager.npcs.values():
            if not _is_hostile(npc) or getattr(npc, "hp", 1) <= 0:
                continue
            if not _colocated(zone_name, npc):
                continue
            nx, ny = npc.position
            d = max(abs(nx - px), abs(ny - py))
            if best is None or d < best:
                best = d
    except Exception:
        pass

    in_town = False
    if not in_dungeon:
        if in_interior:
            in_town = True
        else:
            try:
                in_town = engine.encounter_manager._in_safe_zone((px, py))
            except Exception:
                in_town = False
    is_night = False
    try:
        is_night = engine.world.time_of_day() == "night"
    except Exception:
        pass
    return {
        "in_combat": best is not None and best <= 1,
        "threat_dist": best,
        "in_dungeon": in_dungeon,
        "in_town": in_town,
        "is_night": is_night,
    }


class MusicManager:
    def __init__(self):
        self.enabled = False
        self.moods = {}
        self._sounds = {}
        self._channels = []
        self._cur_ch = None
        self._old_ch = None
        self._cur_mood = None
        self._fade_t = FADE_DUR
        self._since = REEVAL_EVERY
        self.master = MUSIC_MASTER
        if not AUDIO_OK:
            return
        try:
            with open(_DATA, encoding="utf-8") as fh:
                self.moods = json.load(fh)
        except Exception as e:
            logger.info(f"Music data unavailable: {e}")
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(music_synth.SAMPLE_RATE, -16, 1, 512)
            total = pygame.mixer.get_num_channels()
            if total < 16:
                pygame.mixer.set_num_channels(16)
                total = 16
            self._channels = [pygame.mixer.Channel(total - 1),
                              pygame.mixer.Channel(total - 2)]
            self.enabled = True
        except Exception as e:
            logger.info(f"Music disabled: {e}")

    # ---- rendering ------------------------------------------------------

    def _sound_for(self, mood):
        if mood in self._sounds:
            return self._sounds[mood]
        params = self.moods.get(mood)
        if params is None:
            return None
        try:
            seed = sum(ord(c) for c in mood)
            buf = music_synth.render_mood(params, seed=seed)
            pcm = np.clip(buf * self.master, -1, 1)
            snd = pygame.sndarray.make_sound((pcm * 32767).astype(np.int16))
        except Exception as e:
            logger.debug(f"render {mood} failed: {e}")
            snd = None
        self._sounds[mood] = snd
        return snd

    # ---- crossfade ------------------------------------------------------

    def _free_channel(self):
        for ch in self._channels:
            if ch is not self._cur_ch and ch is not self._old_ch:
                return ch
        return self._channels[0] if self._channels else None

    def set_mood(self, mood):
        if not self.enabled or mood == self._cur_mood:
            return
        snd = self._sound_for(mood)
        if snd is None:
            return
        ch = self._free_channel()
        if ch is None:
            return
        try:
            ch.stop()
            ch.play(snd, loops=-1)
            ch.set_volume(0.0)
        except Exception:
            return
        if self._cur_ch is not None and self._cur_ch is not ch:
            self._old_ch = self._cur_ch
        self._cur_ch = ch
        self._cur_mood = mood
        self._fade_t = 0.0

    def update(self, dt):
        """Advance the crossfade. Call every frame."""
        if not self.enabled or self._cur_ch is None:
            return
        if self._fade_t >= FADE_DUR:
            return
        self._fade_t += dt
        k = min(1.0, self._fade_t / FADE_DUR)
        try:
            self._cur_ch.set_volume(k)
            if self._old_ch is not None:
                self._old_ch.set_volume(1.0 - k)
                if k >= 1.0:
                    self._old_ch.stop()
                    self._old_ch = None
        except Exception:
            pass

    # ---- driving from game state ---------------------------------------

    def update_mood(self, engine, dt):
        """Throttled: re-evaluate the mood and honour the setting."""
        if not AUDIO_OK or not self._channels:
            return
        on = True
        try:
            from engine import settings
            on = settings.get_setting(engine.player, "music") == "on"
        except Exception:
            pass
        if not on:
            if self.enabled:
                self.enabled = False
                self._silence()
            return
        if not self.enabled:
            self.enabled = True
            self._cur_mood = None            # restart on re-enable
        self._since += dt
        if self._since < REEVAL_EVERY:
            return
        self._since = 0.0
        try:
            self.set_mood(select_mood(**read_state(engine)))
        except Exception as e:
            logger.debug(f"mood pick failed: {e}")

    def _silence(self):
        for ch in self._channels:
            try:
                ch.stop()
            except Exception:
                pass
        self._cur_ch = self._old_ch = None
        self._cur_mood = None

    def shutdown(self):
        self._silence()
