"""
Reverse Crash — crash reverso (build-up).

Ruido HP filtrado com envelope exponencial crescente.
Simula um prato de bateria tocado ao contrario, classico em transicoes.
"""

import numpy as np
from effects._utils import make_envelope, highpass, bandpass, ensure_stereo, normalize_peak

NAME = "reverse_crash"
LABEL = "Reverse Crash"
DESCRIPTION = "Crash reverso (build-up metalico)"


def generate(duration_samples, sr, **kwargs):
    """Gera reverse crash stereo (2, samples)."""
    n = duration_samples

    # Ruido branco como base
    noise_l = np.random.randn(n)
    noise_r = np.random.randn(n)

    # Bandpass: zona de crash (2kHz-12kHz) — metalico e brilhante
    crash_l = bandpass(noise_l, sr, 2000, 12000)
    crash_r = bandpass(noise_r, sr, 2000, 12000)

    # Adicionar componente mid pra corpo (800Hz-3kHz, mais suave)
    body_l = bandpass(noise_l, sr, 800, 3000) * 0.3
    body_r = bandpass(noise_r, sr, 800, 3000) * 0.3

    crash_l += body_l
    crash_r += body_r

    # Envelope: exponencial crescente (reverso do decay natural de crash)
    t = np.linspace(0, 1, n, endpoint=False)
    # Exponencial mais dramatico que linear
    env = (np.exp(t * 4) - 1) / (np.exp(4) - 1)

    # Fade out rapido nos ultimos 2% (corte no pico, como crash real reverso)
    fadeout_len = max(1, int(n * 0.02))
    env[-fadeout_len:] *= np.linspace(1, 0, fadeout_len)

    crash_l *= env
    crash_r *= env

    out = np.stack([crash_l, crash_r])
    out = normalize_peak(out, 0.9)
    return out
