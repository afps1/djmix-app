"""
Telephone Filter — banda que abre gradualmente.

Ruido com bandpass estreito que expande ao longo da transicao.
Começa tipo "radio AM" (300-3kHz) e vai abrindo ate full range (80-12kHz).
Simula o efeito classico de filtro de telefone se abrindo.
"""

import numpy as np
from effects._utils import make_envelope, bandpass, normalize_peak

NAME = "telephone"
LABEL = "Telephone Filter"
DESCRIPTION = "Banda que abre gradualmente (radio AM → full)"


def generate(duration_samples, sr, **kwargs):
    """Gera telephone filter stereo (2, samples)."""
    n = duration_samples

    # Ruido como base (com corpo, nao so hiss)
    noise_l = np.random.randn(n) * 0.5
    noise_r = np.random.randn(n) * 0.5

    # Dividir em chunks e aplicar bandpass com banda crescente
    n_chunks = 48
    chunk_size = n // n_chunks

    # Banda expandindo: lo desce, hi sobe
    lo_freqs = np.linspace(300, 80, n_chunks)    # 300 → 80 Hz
    hi_freqs = np.linspace(3000, 12000, n_chunks)  # 3kHz → 12kHz

    filtered_l = np.zeros(n)
    filtered_r = np.zeros(n)

    for i in range(n_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < n_chunks - 1 else n
        chunk_l = noise_l[start:end]
        chunk_r = noise_r[start:end]

        lo = lo_freqs[i]
        hi = hi_freqs[i]

        filtered_l[start:end] = bandpass(chunk_l, sr, lo, hi)
        filtered_r[start:end] = bandpass(chunk_r, sr, lo, hi)

    # Adicionar componente tonal sutil pra nao ser so ruido
    t = np.linspace(0, n / sr, n, endpoint=False)
    # Tom de "dial tone" sutil que desvanece
    tone = np.sin(2 * np.pi * 440 * t) * 0.05
    tone *= make_envelope(n, "ramp_down")  # some conforme abre
    filtered_l += tone
    filtered_r += tone

    # Envelope sustain
    env = make_envelope(n, "sustain")
    filtered_l *= env
    filtered_r *= env

    out = np.stack([filtered_l, filtered_r])
    out = normalize_peak(out, 0.9)
    return out
