"""
Impact Clap — clap reverberado no final.

Similar ao sub_boom mas na faixa media/aguda.
~85% silencio + burst de ruido bandpass (1-5kHz) simulando palma/clap
seguido de reverb tail longo. Marca o momento do drop.
"""

import numpy as np
from effects._utils import make_envelope, bandpass, ensure_stereo, normalize_peak
from scipy.signal import fftconvolve

NAME = "impact_clap"
LABEL = "Impact Clap"
DESCRIPTION = "Clap reverberado no final da transicao"


def _make_reverb_ir(sr, decay_sec=1.2, density=2000):
    """Gera impulse response sintetico pra reverb."""
    n = int(decay_sec * sr)
    t = np.linspace(0, decay_sec, n, endpoint=False)

    # Reflexoes aleatorias com decay exponencial
    ir = np.random.randn(n) * np.exp(-t * 4.0 / decay_sec)

    # Primeiras reflexoes mais fortes
    n_early = min(int(0.05 * sr), n)
    if n_early > 0:
        ir[:n_early] *= 2.0

    # Normalizar
    peak = np.max(np.abs(ir))
    if peak > 0:
        ir /= peak

    return ir


def generate(duration_samples, sr, **kwargs):
    """Gera impact clap stereo (2, samples)."""
    n = duration_samples
    out = np.zeros(n)

    # Onset: ~85% da duracao
    onset = int(n * 0.85)
    clap_len = min(int(0.015 * sr), n - onset)  # 15ms de clap

    if clap_len > 0 and onset < n:
        # Clap: burst de ruido bandpass (1-5kHz)
        noise = np.random.randn(clap_len)
        clap = bandpass(noise, sr, 1000, 5000)

        # Envelope do clap: attack instantaneo + decay curto
        t_clap = np.linspace(0, clap_len / sr, clap_len, endpoint=False)
        clap_env = np.exp(-t_clap * 100)  # decay ~10ms
        clap *= clap_env

        out[onset:onset + clap_len] = clap

    # Reverb tail
    if onset < n:
        ir = _make_reverb_ir(sr, decay_sec=1.5)
        # Pegar o segmento do onset ate o final
        dry_segment = out[onset:]
        wet = fftconvolve(dry_segment, ir, mode='full')[:len(dry_segment)]
        out[onset:] = dry_segment + wet * 0.7

    # Build-up sutil antes do clap: ruido crescente
    build_start = max(0, onset - int(n * 0.15))
    build_len = onset - build_start
    if build_len > int(0.1 * sr):
        t_build = np.linspace(0, build_len / sr, build_len, endpoint=False)
        build = np.random.randn(build_len) * 0.03
        build = bandpass(build, sr, 2000, 8000)
        build_env = np.linspace(0, 0.5, build_len) ** 2  # crescente quadratico
        out[build_start:onset] += build * build_env

    out = normalize_peak(out, 0.9)

    # Stereo: leve diferenca de timing no R pra espacialidade
    out_r = np.roll(out, np.random.randint(5, 30))
    # Diferente reverb seed no R
    if onset < n:
        ir_r = _make_reverb_ir(sr, decay_sec=1.6)
        dry_r = np.zeros_like(out_r[onset:])
        if clap_len > 0 and onset + clap_len <= n:
            dry_r[:clap_len] = bandpass(np.random.randn(clap_len), sr, 1000, 5000) * np.exp(-np.linspace(0, clap_len/sr, clap_len) * 100)
        wet_r = fftconvolve(dry_r, ir_r, mode='full')[:len(dry_r)]
        out_r[onset:] = out_r[onset:] * 0.5 + wet_r * 0.5

    out_r = normalize_peak(out_r, 0.9)
    return np.stack([out, out_r])
