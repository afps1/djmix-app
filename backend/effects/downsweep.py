"""
Downsweep — sweep tonal descendente.

Sine wave que varre de 2000Hz ate 80Hz ao longo da duracao.
Cria sensacao de "queda" ou "resolucao", bom pra marcar saida de T1.
"""

import numpy as np
from effects._utils import make_envelope, ensure_stereo, normalize_peak

NAME = "downsweep"
LABEL = "Downsweep"
DESCRIPTION = "Sweep tonal descendente (2kHz a 80Hz)"


def generate(duration_samples, sr, **kwargs):
    """Gera downsweep stereo (2, samples)."""
    n = duration_samples
    t = np.linspace(0, n / sr, n, endpoint=False)

    # Frequencia descendente: 2000 → 80 Hz (exponencial pra soar mais natural)
    f_start = 2000.0
    f_end = 80.0
    # Sweep exponencial: f(t) = f_start * (f_end/f_start)^(t/T)
    duration_sec = n / sr
    freq_t = f_start * (f_end / f_start) ** (t / duration_sec)

    # Fase instantanea (integral da frequencia)
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    sweep = np.sin(phase)

    # Envelope: ramp_down (mais forte no inicio, some no final)
    env = make_envelope(n, "ramp_down")
    # Fade in suave (50ms) pra evitar click
    fade_in = min(int(0.05 * sr), n // 4)
    if fade_in > 0:
        env[:fade_in] *= np.linspace(0, 1, fade_in)

    sweep *= env * 0.7

    # Adicionar harmonico sutil (oitava acima, 30% do volume)
    harmonic = np.sin(phase * 2) * env * 0.2

    out = sweep + harmonic
    out = normalize_peak(out, 0.9)
    return ensure_stereo(out)
