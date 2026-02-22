"""Transição: Filter Sweep — low-pass sweep out + high-pass sweep in."""

import numpy as np
from scipy.signal import butter, sosfilt

NAME = "filter_sweep"
LABEL = "Filter Sweep"
DESCRIPTION = "Low-pass sweep na saída + high-pass sweep na entrada"


def apply(seg1, seg2, sr=44100, **kwargs):
    n = min(seg1.shape[-1], seg2.shape[-1])
    if seg1.ndim == 2:
        out = np.zeros((seg1.shape[0], n))
    else:
        out = np.zeros(n)
    num_chunks = 32
    chunk_size = n // num_chunks
    for i in range(num_chunks):
        s = i * chunk_size
        # Último chunk vai até o final exato (sem pular samples residuais)
        e = (i + 1) * chunk_size if i < num_chunks - 1 else n
        # progress: 0.0 no início → 1.0 no final (último chunk incluso)
        progress = i / (num_chunks - 1) if num_chunks > 1 else 1.0
        cutoff = min(20000 * (1 - progress) + 200 * progress, sr * 0.45)
        sos = butter(4, cutoff, btype='low', fs=sr, output='sos')
        c1 = seg1[..., s:e]
        c2 = seg2[..., s:e]
        if seg1.ndim == 2:
            filtered = np.stack([sosfilt(sos, c1[ch]) for ch in range(c1.shape[0])])
        else:
            filtered = sosfilt(sos, c1)
        out[..., s:e] = filtered * (1.0 - progress) + c2 * progress
    return out
