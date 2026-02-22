"""
Vinyl Crackle — textura analogica com pops e estalidos.

Simula o som de um disco de vinil com crackle aleatorio e LP filter.
Cria uma textura sutil que preenche a transicao sem chamar atencao.
"""

import numpy as np
from effects._utils import make_envelope, lowpass, ensure_stereo, normalize_peak

NAME = "vinyl_crackle"
LABEL = "Vinyl Crackle"
DESCRIPTION = "Textura analogica (estalidos de vinil)"


def generate(duration_samples, sr, **kwargs):
    """Gera vinyl crackle stereo (2, samples)."""
    n = duration_samples

    # Base: ruido rosa (enfatiza graves)
    white = np.random.randn(n)
    # Aproximacao de ruido rosa via filtro
    pink = lowpass(white, sr, 4000) * 0.1

    # Pops/estalidos aleatorios
    # Densidade: ~8-15 pops por segundo
    pops_per_sec = np.random.uniform(8, 15)
    n_pops = int(pops_per_sec * n / sr)
    pop_positions = np.random.randint(0, n, size=n_pops)

    pops = np.zeros(n)
    for pos in pop_positions:
        # Cada pop: impulso curto com decay
        pop_len = np.random.randint(int(0.0005 * sr), int(0.003 * sr))  # 0.5-3ms
        pop_amp = np.random.uniform(0.3, 1.0)
        end = min(pos + pop_len, n)
        actual_len = end - pos
        if actual_len > 1:
            pop = np.random.randn(actual_len) * pop_amp
            pop *= np.exp(-np.linspace(0, 10, actual_len))  # decay rapido
            pops[pos:end] += pop

    # Combinar
    crackle = pink + pops * 0.4

    # LP filter pra som mais "quente"
    crackle = lowpass(crackle, sr, 6000)

    # Envelope sustain (fade in/out suave)
    env = make_envelope(n, "sustain")
    crackle *= env

    crackle = normalize_peak(crackle, 0.9)

    # Stereo: mesmo crackle mas com timing levemente diferente no R
    crackle_r = np.roll(crackle, np.random.randint(10, 100))
    # Adicionar pops extras no R pra diferenciacao
    extra_pops = np.zeros(n)
    n_extra = int(pops_per_sec * 0.3 * n / sr)
    for pos in np.random.randint(0, n, size=n_extra):
        pop_len = np.random.randint(int(0.0005 * sr), int(0.002 * sr))
        end = min(pos + pop_len, n)
        actual_len = end - pos
        if actual_len > 1:
            extra_pops[pos:end] += np.random.randn(actual_len) * 0.2 * np.exp(-np.linspace(0, 10, actual_len))
    crackle_r += lowpass(extra_pops, sr, 6000) * env * 0.3

    return np.stack([crackle, crackle_r])
