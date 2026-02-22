"""
Noise Riser — sweep de ruido ascendente.

Ruido branco com filtro LP que varre de 200Hz ate 8000Hz ao longo da duracao.
Cria tensao crescente, classico em transicoes EDM.
"""

import numpy as np
from effects._utils import make_envelope, lowpass, ensure_stereo, normalize_peak

NAME = "noise_riser"
LABEL = "Noise Riser"
DESCRIPTION = "Sweep de ruido ascendente (build-up)"


def generate(duration_samples, sr, **kwargs):
    """Gera noise riser stereo (2, samples)."""
    n = duration_samples

    # Ruido branco
    noise = np.random.randn(n) * 0.5

    # LP sweep: 200Hz → 8000Hz
    # Dividir em chunks e aplicar filtro com cutoff progressivo
    n_chunks = 64
    chunk_size = n // n_chunks
    freqs = np.linspace(200, 8000, n_chunks)
    filtered = np.zeros(n)

    for i in range(n_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < n_chunks - 1 else n
        chunk = noise[start:end]
        filtered[start:end] = lowpass(chunk, sr, freqs[i])

    # Envelope crescente (swell)
    env = make_envelope(n, "swell")
    filtered *= env

    # Normalizar e stereo
    filtered = normalize_peak(filtered, 0.9)

    # Leve diferenca stereo pra espacialidade
    noise_r = np.random.randn(n) * 0.5
    filtered_r = np.zeros(n)
    for i in range(n_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < n_chunks - 1 else n
        chunk = noise_r[start:end]
        filtered_r[start:end] = lowpass(chunk, sr, freqs[i])
    filtered_r *= env
    filtered_r = normalize_peak(filtered_r, 0.9)

    return np.stack([filtered, filtered_r])
