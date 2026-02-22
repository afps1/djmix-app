"""
White Noise Wash — textura de ruido constante.

Ruido branco filtrado com LP ~6kHz, envelope sustain (fade in/out suave).
Cria uma textura de "mar" que preenche a transicao sem chamar atencao.
Diferente do noise_riser que sobe — este mantém nivel constante.
"""

import numpy as np
from effects._utils import make_envelope, lowpass, ensure_stereo, normalize_peak

NAME = "white_wash"
LABEL = "White Noise Wash"
DESCRIPTION = "Textura de ruido constante (tipo mar)"


def generate(duration_samples, sr, **kwargs):
    """Gera white noise wash stereo (2, samples)."""
    n = duration_samples

    # Ruido branco independente L/R pra espacialidade
    noise_l = np.random.randn(n) * 0.5
    noise_r = np.random.randn(n) * 0.5

    # LP filter: corta acima de 6kHz pra som mais quente
    wash_l = lowpass(noise_l, sr, 6000)
    wash_r = lowpass(noise_r, sr, 6000)

    # Envelope sustain: fade in/out suave (5%)
    env = make_envelope(n, "sustain")
    wash_l *= env
    wash_r *= env

    out = np.stack([wash_l, wash_r])
    out = normalize_peak(out, 0.9)
    return out
