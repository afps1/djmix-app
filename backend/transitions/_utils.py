"""
Helpers compartilhados entre transições.
Prefixo _ no nome do arquivo pra auto-discovery ignorar.
"""

import numpy as np
from scipy.signal import butter, sosfilt


def make_fade(n, ndim):
    """Gera arrays de fade_out e fade_in com broadcast correto pra stereo."""
    fo = np.linspace(1.0, 0.0, n)
    fi = np.linspace(0.0, 1.0, n)
    if ndim == 2:
        fo = fo[np.newaxis, :]
        fi = fi[np.newaxis, :]
    return fo, fi


def split_bands(sig, sr, low_cut=250, high_cut=2500):
    """Butterworth 4ª ordem, split em 3 bandas (low, mid, hi)."""
    nyq = sr * 0.49
    low_cut = min(low_cut, nyq)
    high_cut = min(high_cut, nyq)
    sos_lo = butter(4, low_cut, btype='low', fs=sr, output='sos')
    sos_hi = butter(4, high_cut, btype='high', fs=sr, output='sos')
    sos_mid = butter(4, [low_cut, high_cut], btype='band', fs=sr, output='sos')

    def filt(sos, x):
        if x.ndim == 2:
            return np.stack([sosfilt(sos, x[ch]) for ch in range(x.shape[0])])
        return sosfilt(sos, x)

    return filt(sos_lo, sig), filt(sos_mid, sig), filt(sos_hi, sig)
