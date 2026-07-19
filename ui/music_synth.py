"""Procedural MUSIC synthesis (pure numpy — no audio assets).

True to the procedural-audio ethos of `ui/sound.py`: every note is
synthesized. This module is the *theory + waveform* layer — it returns
float arrays and knows nothing about pygame, so it is fully
headless-testable. `ui/music.py` renders these to loopable Sounds and
drives the adaptive playback.

A "mood" (data/music.json) names a root note, a scale, a tempo and the
layers to stack: a sustained PAD (the chord bed), a plucked ARP (the
melody), a BASS pulse. Modal/pentatonic scales + consonant chords keep
even a random walk pleasant.
"""

import numpy as np

SAMPLE_RATE = 22050
BEATS_PER_BAR = 4

# semitone offsets within an octave
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],           # aeolian
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "pent_minor": [0, 3, 5, 7, 10],
    "pent_major": [0, 2, 4, 7, 9],
}


def midi_to_freq(m: float) -> float:
    """MIDI note number → Hz (A4 = 69 = 440 Hz)."""
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def _scale_notes(root_midi, scale, octaves):
    """The scale laid out across `octaves`, as MIDI numbers."""
    out = []
    for o in range(octaves):
        for s in scale:
            out.append(root_midi + 12 * o + s)
    return np.array(out, dtype=float)


def _samples_for(bpm, bars):
    beats = bars * BEATS_PER_BAR
    return int(SAMPLE_RATE * beats * 60.0 / bpm)


def pad(root_midi, scale, n, volume=0.32):
    """A sustained chord bed (root/third/fifth + octave) with a slow
    amplitude drift so it breathes. Continuous — the loop seam is fixed
    by `_loop_blend`."""
    degs = [0, 2, 4]
    notes = [root_midi + scale[d % len(scale)] + 12 * (d // len(scale))
             for d in degs]
    notes.append(root_midi + 12)
    t = np.arange(n) / SAMPLE_RATE
    wave = np.zeros(n)
    for i, m in enumerate(notes):
        f = midi_to_freq(m)
        detune = 1.0 + 0.0018 * (i - 1)        # slight chorus warmth
        lfo = 0.82 + 0.18 * np.sin(2 * np.pi * (0.05 + 0.013 * i) * t + i)
        wave += np.sin(2 * np.pi * f * detune * t) * lfo
    return wave / len(notes) * volume


def _pluck(freq, n):
    """A short plucked tone: fast attack, exponential decay to ~0."""
    if n <= 0:
        return np.zeros(0)
    t = np.arange(n) / SAMPLE_RATE
    dur = n / SAMPLE_RATE
    env = np.exp(-3.6 * t / dur)
    a = max(1, int(n * 0.02))
    env[:a] *= np.linspace(0, 1, a)            # kill the onset click
    return (np.sin(2 * np.pi * freq * t)
            + 0.3 * np.sin(2 * np.pi * 2 * freq * t)) * env


def arpeggio(root_midi, scale, bpm, bars, seed, volume=0.22,
             octaves=2, subdiv=2, rest_chance=0.18):
    """A seeded melodic random-walk over the scale — deterministic per
    (mood, seed), so it is reproducible and testable."""
    n = _samples_for(bpm, bars)
    beats = bars * BEATS_PER_BAR
    steps = max(1, beats * subdiv)
    step_n = n // steps
    out = np.zeros(n)
    rng = np.random.default_rng(seed)
    ext = _scale_notes(root_midi, scale, octaves)
    pos = len(ext) // 2
    for st in range(steps):
        if rng.random() < rest_chance:
            continue
        pos = int(np.clip(pos + rng.integers(-2, 3), 0, len(ext) - 1))
        note = _pluck(midi_to_freq(ext[pos]), int(step_n * 1.6))
        a = st * step_n
        b = min(n, a + len(note))
        out[a:b] += note[:b - a] * volume
    return out


def _bass_note(freq, n):
    if n <= 0:
        return np.zeros(0)
    t = np.arange(n) / SAMPLE_RATE
    dur = n / SAMPLE_RATE
    env = np.minimum(1.0, np.exp(-2.2 * t / dur) * 1.1)
    a = max(1, int(n * 0.03))
    env[:a] *= np.linspace(0, 1, a)
    return (np.sin(2 * np.pi * freq * t)
            + 0.25 * np.sin(2 * np.pi * 2 * freq * t)) * env


def bassline(root_midi, scale, bpm, bars, volume=0.3):
    """A low root/fifth pulse on the beat."""
    n = _samples_for(bpm, bars)
    beats = bars * BEATS_PER_BAR
    beat_n = n // beats
    out = np.zeros(n)
    fifth = root_midi + scale[4 % len(scale)]
    pattern = [root_midi - 12, root_midi - 12, fifth - 12, root_midi - 12]
    for bt in range(beats):
        note = _bass_note(midi_to_freq(pattern[bt % len(pattern)]), beat_n)
        a = bt * beat_n
        b = min(n, a + len(note))
        out[a:b] += note[:b - a] * volume
    return out


def _loop_blend(wave, n, x):
    """Make `wave[:n]` seamless by blending its head with the natural
    continuation past n (rendered into wave[n:n+x])."""
    x = min(x, n // 4, max(0, len(wave) - n))
    loop = wave[:n].copy()
    if x <= 0:
        return loop
    fade = np.linspace(0.0, 1.0, x)
    loop[:x] = wave[n:n + x] * (1 - fade) + wave[:x] * fade
    return loop


def render_mood(params, seed=0):
    """Render one mood to a loopable float32 buffer in [-1, 1]."""
    bpm = float(params.get("bpm", 68))
    bars = int(params.get("bars", 4))
    root = int(params.get("root", 57))                 # A3
    scale = SCALES.get(params.get("scale", "minor"), SCALES["minor"])
    layers = params.get("layers", ["pad", "bass"])
    n = _samples_for(bpm, bars)
    x = int(SAMPLE_RATE * 0.06)
    edge = min(int(SAMPLE_RATE * 0.04), n // 4)
    mix = np.zeros(n)
    # the PAD is continuous: render one crossfade window past the loop and
    # blend, so it wraps seamlessly.
    if "pad" in layers:
        mix += _loop_blend(pad(root, scale, n + x,
                               params.get("pad_vol", 0.32)), n, x)
    # EVENT layers start from silence (note attacks) — taper their tails to
    # silence too, so the loop boundary carries no click from a hanging note.
    for name, fn in (
        ("bass", lambda: bassline(root, scale, bpm, bars,
                                  params.get("bass_vol", 0.30))),
        ("arp", lambda: arpeggio(root, scale, bpm, bars, seed,
                                 params.get("arp_vol", 0.22),
                                 params.get("arp_octaves", 2)))):
        if name in layers:
            w = fn()[:n].copy()
            if edge > 0:
                w[-edge:] *= np.linspace(1.0, 0.0, edge)
            mix += w
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 0.92 * float(params.get("volume", 1.0))
    return mix.astype(np.float32)
