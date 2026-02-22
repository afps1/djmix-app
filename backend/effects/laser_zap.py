"""
Laser Zap — sweeps rapidos ascendentes repetidos.

Cada "zap" e um sine sweep rapido (~200→4000Hz em ~80ms).
Repetido ao longo da transicao com densidade crescente.
Efeito futurista/sci-fi que adiciona energia progressiva.
"""

import numpy as np
from effects._utils import make_envelope, normalize_peak

NAME = "laser_zap"
LABEL = "Laser Zap"
DESCRIPTION = "Sweeps rapidos ascendentes (sci-fi)"


def _make_zap(sr, freq_start=200, freq_end=4000, dur_ms=80):
    """Gera um unico zap: sine sweep rapido com decay."""
    n = int(dur_ms / 1000 * sr)
    if n < 10:
        return np.zeros(10)
    t = np.linspace(0, dur_ms / 1000, n, endpoint=False)

    # Sweep exponencial
    duration_sec = dur_ms / 1000
    freq_t = freq_start * (freq_end / freq_start) ** (t / duration_sec)
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    zap = np.sin(phase)

    # Envelope: attack instantaneo + decay exponencial
    env = np.exp(-t * 30)  # decay rapido
    zap *= env

    return zap


def generate(duration_samples, sr, **kwargs):
    """Gera laser zaps stereo (2, samples)."""
    n = duration_samples
    out_l = np.zeros(n)
    out_r = np.zeros(n)

    duration_sec = n / sr

    # Calcular posicoes dos zaps: espaçamento decrescente (mais densos no final)
    # Usar funcao quadratica invertida pra distribuir
    n_zaps = max(4, int(duration_sec * 2.5))  # ~2.5 zaps/segundo
    # Posicoes normalizadas: concentradas no final
    t_norm = np.linspace(0, 1, n_zaps + 2)[1:-1]  # excluir extremos
    # Curva quadratica: mais espaco no inicio, menos no final
    positions = (t_norm ** 0.6) * n  # expoente <1 = mais concentrado no final
    positions = positions.astype(int)

    # Intensidade crescente
    intensities = np.linspace(0.2, 1.0, len(positions))

    for i, (pos, intensity) in enumerate(zip(positions, intensities)):
        # Variar duração do zap (60-100ms)
        dur_ms = np.random.uniform(60, 100)
        zap = _make_zap(sr, freq_start=180 + i * 5, freq_end=3500 + i * 50, dur_ms=dur_ms)
        zap_len = len(zap)

        if pos + zap_len > n:
            zap_len = n - pos
            zap = zap[:zap_len]

        if zap_len > 0:
            # L: zap normal, R: leve detune (pitch ligeiramente diferente)
            out_l[pos:pos + zap_len] += zap * intensity
            # Detune no R: usar frequencia ligeiramente maior
            zap_r = _make_zap(sr, freq_start=190 + i * 5, freq_end=3600 + i * 50, dur_ms=dur_ms)
            zap_r = zap_r[:zap_len]
            out_r[pos:pos + zap_len] += zap_r * intensity * 0.9

    # Envelope global crescente
    env = make_envelope(n, "swell")
    out_l *= env
    out_r *= env

    out = np.stack([out_l, out_r])
    out = normalize_peak(out, 0.9)
    return out
