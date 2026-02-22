"""Transição: Reverb Wash — reverb longo na track 1 com fade pra track 2."""

import numpy as np
from scipy.signal import fftconvolve
from transitions._utils import make_fade

NAME = "reverb_wash"
LABEL = "Reverb Wash"
DESCRIPTION = "Reverberação longa na track de saída criando atmosfera, com fade pra track de entrada"


def _generate_ir(sr, decay_sec=3.0, predelay_ms=20):
    """Gera impulse response sintético (reverb estilo hall grande)."""
    predelay_samples = int(predelay_ms / 1000 * sr)
    decay_samples = int(decay_sec * sr)
    total = predelay_samples + decay_samples

    # Noise com decay exponencial
    noise = np.random.randn(decay_samples)
    decay = np.exp(-np.linspace(0, 6, decay_samples))  # -60dB em decay_sec
    ir = noise * decay

    # Suavizar o início (evita transiente brusco)
    attack = min(int(0.005 * sr), len(ir))
    ir[:attack] *= np.linspace(0, 1, attack)

    # Predelay
    ir = np.concatenate([np.zeros(predelay_samples), ir])

    # Normalizar
    peak = np.max(np.abs(ir))
    if peak > 0:
        ir /= peak

    return ir


def apply(seg1, seg2, sr=44100, **kwargs):
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]

    # Gerar impulse response
    ir = _generate_ir(sr, decay_sec=2.5, predelay_ms=15)

    # Aplicar reverb via convolução
    if s1.ndim == 2:
        reverbed = np.stack([
            fftconvolve(s1[ch], ir, mode='full')[:n] for ch in range(s1.shape[0])
        ])
    else:
        reverbed = fftconvolve(s1, ir, mode='full')[:n]

    # Normalizar reverb pro mesmo nível do original
    peak_orig = np.max(np.abs(s1))
    peak_rev = np.max(np.abs(reverbed))
    if peak_rev > 0:
        reverbed = reverbed * (peak_orig / peak_rev) * 0.8  # -2dB pra não dominar

    # Mix: dry→wet gradual na T1, depois fade out do wet enquanto T2 sobe
    t = np.linspace(0.0, 1.0, n)
    if s1.ndim == 2:
        t = t[np.newaxis, :]

    # T1: começa dry, vai ficando wet, depois faz fade out
    dry_amount = np.clip(1.0 - t * 2.0, 0, 1)      # dry some até 50%
    wet_amount = np.clip(t * 2.0, 0, 1) * np.clip(1.0 - (t - 0.4) * 2.0, 0, 1)  # wet cresce e depois cai
    t1_mixed = s1 * dry_amount + reverbed * wet_amount

    # T1 fade out geral
    t1_fade = np.clip(1.0 - (t - 0.3) * 1.5, 0, 1)
    t1_mixed = t1_mixed * t1_fade

    # T2 fade in
    t2_fade = np.clip((t - 0.2) * 1.5, 0, 1)
    t2_in = s2 * t2_fade

    out = t1_mixed + t2_in

    peak = np.max(np.abs(out))
    if peak > 1.0:
        out /= peak
    return out
