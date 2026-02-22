"""
Tension Pad — pad tonal sustentado com LFO.

Soma de sines formando um acorde suspensivo (notas ambiguas)
com modulacao LFO lenta pra criar tensao. Envelope triangle (swell + decay).
"""

import numpy as np
from effects._utils import make_envelope, ensure_stereo, normalize_peak

NAME = "tension_pad"
LABEL = "Tension Pad"
DESCRIPTION = "Pad tonal sustentado com modulacao"


def generate(duration_samples, sr, **kwargs):
    """Gera tension pad stereo (2, samples)."""
    n = duration_samples
    t = np.linspace(0, n / sr, n, endpoint=False)

    # Acorde suspensivo: frequencias que criam tensao sem resolver
    # Baseado em intervalos de 5a e 4a (notas neutras harmonicamente)
    freqs = [110, 165, 220, 330]  # A2, E3, A3, E4
    amplitudes = [0.4, 0.3, 0.25, 0.15]

    pad_l = np.zeros(n)
    pad_r = np.zeros(n)

    for i, (freq, amp) in enumerate(zip(freqs, amplitudes)):
        # Leve detune entre L e R pra espacialidade
        detune = 0.5 * (i + 1)  # 0.5-2 Hz de diferenca
        pad_l += np.sin(2 * np.pi * freq * t) * amp
        pad_r += np.sin(2 * np.pi * (freq + detune) * t) * amp

    # LFO: modulacao lenta de amplitude (tremolo)
    lfo_rate = 0.3  # 0.3 Hz — bem lento
    lfo = 0.7 + 0.3 * np.sin(2 * np.pi * lfo_rate * t)
    pad_l *= lfo
    pad_r *= lfo

    # Envelope triangle (swell no meio)
    env = make_envelope(n, "triangle")
    # Suavizar com fade mais longo (100ms)
    fade = min(int(0.1 * sr), n // 4)
    if fade > 0:
        env[:fade] = np.minimum(env[:fade], np.linspace(0, 1, fade))
        env[-fade:] = np.minimum(env[-fade:], np.linspace(1, 0, fade))

    pad_l *= env
    pad_r *= env

    out = np.stack([pad_l, pad_r])
    out = normalize_peak(out, 0.9)
    return out
