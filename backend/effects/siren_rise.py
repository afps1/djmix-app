"""
Siren Rise — sirene ascendente.

Sine wave com pitch ascendente lento (200→2000Hz) e vibrato LFO
que da o carater de sirene. Classico em transicoes EDM/Big Room.
"""

import numpy as np
from effects._utils import make_envelope, ensure_stereo, normalize_peak

NAME = "siren_rise"
LABEL = "Siren Rise"
DESCRIPTION = "Sirene ascendente com vibrato"


def generate(duration_samples, sr, **kwargs):
    """Gera siren rise stereo (2, samples)."""
    n = duration_samples
    t = np.linspace(0, n / sr, n, endpoint=False)
    duration_sec = n / sr

    # Frequencia base: 200 → 2000 Hz (exponencial pra soar mais natural)
    f_start = 200.0
    f_end = 2000.0
    base_freq = f_start * (f_end / f_start) ** (t / duration_sec)

    # Vibrato LFO: oscilacao de ±30Hz a 5Hz
    lfo_rate = 5.0
    lfo_depth = 30.0  # Hz
    vibrato = lfo_depth * np.sin(2 * np.pi * lfo_rate * t)

    # Frequencia instantanea = base + vibrato
    freq_t = base_freq + vibrato

    # Fase instantanea
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    siren = np.sin(phase)

    # Harmonico sutil (oitava acima, 20%) pra corpo
    harmonic = np.sin(phase * 2) * 0.2

    out = siren + harmonic

    # Envelope swell crescente
    env = make_envelope(n, "swell")
    # Fade in suave (80ms)
    fade = min(int(0.08 * sr), n // 4)
    if fade > 0:
        env[:fade] *= np.linspace(0, 1, fade)
    # Fade out curto (30ms) pra corte limpo
    fadeout = min(int(0.03 * sr), n // 8)
    if fadeout > 0:
        env[-fadeout:] *= np.linspace(1, 0, fadeout)

    out *= env

    out = normalize_peak(out, 0.9)

    # Stereo: leve detune no R pra largura
    freq_r = base_freq + vibrato * 1.1 + 1.5  # +1.5Hz detune
    phase_r = 2 * np.pi * np.cumsum(freq_r) / sr
    siren_r = np.sin(phase_r) + np.sin(phase_r * 2) * 0.2
    siren_r *= env
    siren_r = normalize_peak(siren_r, 0.9)

    return np.stack([out, siren_r])
