"""
Shimmer Rise — harmonicos agudos ascendentes.

Camadas de sines na faixa aguda (2-8kHz) com pitch shift lento
ascendente ao longo da transicao. Efeito etereo e brilhante.
Mais sutil que noise_riser, foco na faixa de "brilho".
"""

import numpy as np
from effects._utils import make_envelope, normalize_peak

NAME = "shimmer_rise"
LABEL = "Shimmer Rise"
DESCRIPTION = "Harmonicos agudos ascendentes (etereo)"


def generate(duration_samples, sr, **kwargs):
    """Gera shimmer rise stereo (2, samples)."""
    n = duration_samples
    t = np.linspace(0, n / sr, n, endpoint=False)

    # Camadas de harmonicos com pitch ascendente
    # Frequencias base: 2kHz, 3kHz, 4.5kHz, 6kHz
    base_freqs = [2000, 3000, 4500, 6000]
    # Pitch shift: sobe ~50% ao longo da duracao
    pitch_mult = np.linspace(1.0, 1.5, n)

    pad_l = np.zeros(n)
    pad_r = np.zeros(n)

    for i, base_f in enumerate(base_freqs):
        # Frequencia instantanea com pitch shift
        freq_t = base_f * pitch_mult
        phase = 2 * np.pi * np.cumsum(freq_t) / sr

        # Amplitude decrescente por oitava
        amp = 0.4 / (i + 1)

        # Chorus: detune entre L e R (~3Hz)
        detune_hz = 2.0 + i * 0.8
        pad_l += np.sin(phase) * amp
        pad_r += np.sin(phase + 2 * np.pi * detune_hz * t) * amp

    # LFO sutil pra movimento (tremolo lento)
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * t)
    pad_l *= lfo
    pad_r *= lfo

    # Envelope swell: cresce ao longo da transicao
    env = make_envelope(n, "swell")
    # Fade in suave (100ms)
    fade = min(int(0.1 * sr), n // 4)
    if fade > 0:
        env[:fade] *= np.linspace(0, 1, fade)
    # Fade out curto no final (50ms)
    fadeout = min(int(0.05 * sr), n // 8)
    if fadeout > 0:
        env[-fadeout:] *= np.linspace(1, 0, fadeout)

    pad_l *= env
    pad_r *= env

    out = np.stack([pad_l, pad_r])
    out = normalize_peak(out, 0.9)
    return out
