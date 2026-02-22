"""
Helpers de sintese compartilhados entre os efeitos de transicao.
"""

import numpy as np
from scipy.signal import butter, sosfilt


def make_envelope(n, shape="ramp_up"):
    """
    Gera envelope de volume com n samples.

    Shapes disponiveis:
    - ramp_up:   0 → 1 linear (build-up)
    - ramp_down: 1 → 0 linear (fade-out)
    - triangle:  0 → 1 → 0 (swell no meio)
    - swell:     0 → 1 exponencial (mais dramatico que ramp_up)
    - impact:    80% silencio → boom no final
    - sustain:   fade in 5% → sustain → fade out 5%
    """
    if n < 2:
        return np.ones(n)

    t = np.linspace(0, 1, n, endpoint=False)

    if shape == "ramp_up":
        return t

    elif shape == "ramp_down":
        return 1.0 - t

    elif shape == "triangle":
        return np.where(t < 0.5, t * 2, (1.0 - t) * 2)

    elif shape == "swell":
        # Exponencial: lento no inicio, rapido no final
        return (np.exp(t * 3) - 1) / (np.exp(3) - 1)

    elif shape == "impact":
        # 80% silencio, depois boom
        env = np.zeros(n)
        onset = int(n * 0.8)
        remaining = n - onset
        if remaining > 0:
            # Subida rapida + decay
            attack = min(int(remaining * 0.15), remaining)
            if attack > 0:
                env[onset:onset + attack] = np.linspace(0, 1, attack)
            if onset + attack < n:
                decay_len = n - (onset + attack)
                env[onset + attack:] = np.exp(-np.linspace(0, 4, decay_len))
        return env

    elif shape == "sustain":
        # Fade in 5% → sustain pleno → fade out 5%
        fade = max(1, int(n * 0.05))
        env = np.ones(n)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        return env

    else:
        return np.ones(n)


def bandpass(signal, sr, lo, hi, order=4):
    """Butterworth bandpass filter."""
    nyq = sr * 0.49
    lo = max(lo, 1.0)
    hi = min(hi, nyq)
    if lo >= hi:
        return signal
    sos = butter(order, [lo, hi], btype='band', fs=sr, output='sos')
    return sosfilt(sos, signal)


def lowpass(signal, sr, cutoff, order=4):
    """Butterworth lowpass filter."""
    nyq = sr * 0.49
    cutoff = min(cutoff, nyq)
    if cutoff <= 0:
        return np.zeros_like(signal)
    sos = butter(order, cutoff, btype='low', fs=sr, output='sos')
    return sosfilt(sos, signal)


def highpass(signal, sr, cutoff, order=4):
    """Butterworth highpass filter."""
    nyq = sr * 0.49
    cutoff = min(cutoff, nyq)
    if cutoff <= 0:
        return signal
    sos = butter(order, cutoff, btype='high', fs=sr, output='sos')
    return sosfilt(sos, signal)


def ensure_stereo(audio):
    """Garante formato stereo (2, samples)."""
    if audio.ndim == 1:
        return np.stack([audio, audio])
    return audio


def normalize_peak(audio, target=0.9):
    """Normaliza pelo pico."""
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio * (target / peak)
    return audio
