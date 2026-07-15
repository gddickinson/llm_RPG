"""Procedural sound (P5.5) — no audio asset files, true to the
procedural-sprite ethos: every effect is synthesized with numpy at
startup.

SFX are driven by the event log (an observer keyword map), ambience by
the current weather (rain/storm noise loops). Everything degrades
silently when the mixer is unavailable (headless, tests, CI).
"""

import logging

try:
    import numpy as np
    import pygame
    AUDIO_OK = True
except ImportError:  # pragma: no cover
    AUDIO_OK = False

logger = logging.getLogger("llm_rpg.sound")

SAMPLE_RATE = 22050
MASTER_VOLUME = 0.35


def _envelope(n, attack=0.02, release=0.6):
    env = np.ones(n)
    a = max(1, int(n * attack))
    r = max(1, int(n * release))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    return env


def _tone(freq, dur, volume=0.5, shape="sine"):
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    if shape == "square":
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    else:
        wave = np.sin(2 * np.pi * freq * t)
    return wave * _envelope(n) * volume


def _sweep(f0, f1, dur, volume=0.5):
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    freq = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    return np.sin(phase) * _envelope(n) * volume


def _noise(dur, volume=0.3, smooth=1):
    n = int(SAMPLE_RATE * dur)
    data = np.random.default_rng(7).uniform(-1, 1, n)
    if smooth > 1:
        kernel = np.ones(smooth) / smooth
        data = np.convolve(data, kernel, mode="same")
    return data * _envelope(n) * volume


def _to_sound(wave):
    clipped = np.clip(wave * MASTER_VOLUME, -1, 1)
    return pygame.sndarray.make_sound(
        (clipped * 32767).astype(np.int16))


class SoundManager:
    """Synthesized SFX + weather ambience."""

    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self._ambient_kind = None
        self._ambient_channel = None
        if not AUDIO_OK:
            return
        try:
            # A mixer may already be initialized (pygame.init()) with a
            # stereo format our mono buffers don't match — re-init with
            # explicit parameters
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            self._build()
            self.enabled = True
        except Exception as e:
            logger.info(f"Sound disabled: {e}")

    def _build(self):
        self.sounds = {
            "hit": _to_sound(_tone(95, 0.09, 0.9, "square")
                             + _noise(0.09, 0.5)),
            "pickup": _to_sound(_sweep(500, 900, 0.10, 0.5)),
            "coin": _to_sound(np.concatenate([
                _tone(1180, 0.05, 0.5), _tone(1560, 0.07, 0.4)])),
            "levelup": _to_sound(np.concatenate([
                _tone(523, 0.09, 0.5), _tone(659, 0.09, 0.5),
                _tone(784, 0.16, 0.6)])),
            "spell": _to_sound(_sweep(1300, 250, 0.22, 0.5)),
            "discover": _to_sound(np.concatenate([
                _tone(880, 0.08, 0.4), _tone(1174, 0.14, 0.5)])),
            "defeat": _to_sound(_sweep(300, 70, 0.5, 0.7)),
            "rain": _to_sound(_noise(2.0, 0.25, smooth=6)),
            "storm": _to_sound(_noise(2.0, 0.45, smooth=3)),
        }

    # ---- SFX by event keyword ------------------------------------------

    _KEYWORD_MAP = (
        ("** Level up", "levelup"),
        ("level up!", "levelup"),
        ("[Collection]", "discover"),
        ("[Legend]", "discover"),
        ("tier complete", "levelup"),
        ("You pick up", "pickup"),
        ("You forage", "pickup"),
        ("You mine", "pickup"),
        ("You chop", "pickup"),
        ("You fish", "pickup"),
        ("You buy", "coin"),
        ("You sell", "coin"),
        ("quest point", "coin"),
        ("strikes you down", "defeat"),
        ("is defeated!", "hit"),
        ("damage", "hit"),
        ("with Fireball", "spell"),
        ("casts", "spell"),
    )

    def on_event(self, text: str) -> None:
        if not self.enabled:
            return
        for keyword, name in self._KEYWORD_MAP:
            if keyword in text:
                self.play(name)
                return

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            try:
                sound.play()
            except Exception:
                pass

    # ---- ambience -------------------------------------------------------

    def update_ambient(self, weather: str) -> None:
        """Loop rain/storm noise while that weather holds."""
        if not self.enabled:
            return
        kind = weather if weather in ("rain", "storm") else None
        if kind == self._ambient_kind:
            return
        if self._ambient_channel is not None:
            try:
                self._ambient_channel.stop()
            except Exception:
                pass
            self._ambient_channel = None
        self._ambient_kind = kind
        if kind is not None:
            try:
                self._ambient_channel = self.sounds[kind].play(loops=-1)
            except Exception:
                self._ambient_channel = None

    def shutdown(self) -> None:
        if self.enabled:
            try:
                pygame.mixer.stop()
            except Exception:
                pass
