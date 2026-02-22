"""Transição: Sidechain Pump — track 2 entra pumpando no ritmo do BPM."""

import numpy as np
from transitions._utils import make_fade

NAME = "sidechain_pump"
LABEL = "Sidechain Pump"
DESCRIPTION = "Track 2 entra com efeito de pump rítmico sincronizado ao BPM"


def apply(seg1, seg2, sr=44100, **kwargs):
    bpm = kwargs.get("bpm", 128.0)
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]

    beat_samples = int(60.0 / bpm * sr)

    # Criar envelope de pump pra T2
    # Cada beat: duck rápido (attack ~5ms) + release lento (~70% do beat)
    attack_samples = int(0.005 * sr)
    release_samples = int(beat_samples * 0.7)

    pump_env = np.ones(n)
    t_progress = np.linspace(0.0, 1.0, n)  # progresso da transição 0→1

    sample = 0
    while sample < n:
        # Depth do duck diminui ao longo da transição (de -18dB pra 0dB)
        progress = sample / n
        duck_depth = max(0.0, 1.0 - progress) * 0.87  # 0.87 ≈ -18dB

        # Attack (duck rápido)
        att_end = min(sample + attack_samples, n)
        att_len = att_end - sample
        if att_len > 0:
            pump_env[sample:att_end] = 1.0 - duck_depth

        # Release (volta suave)
        rel_start = att_end
        rel_end = min(rel_start + release_samples, n)
        rel_len = rel_end - rel_start
        if rel_len > 0:
            release_curve = np.linspace(1.0 - duck_depth, 1.0, rel_len)
            # Curva exponencial pra release mais natural
            release_curve = 1.0 - duck_depth * (1.0 - np.linspace(0, 1, rel_len) ** 2)
            pump_env[rel_start:rel_end] = release_curve

        sample += beat_samples

    # Aplicar: T1 fade out + T2 com pump
    fo, fi = make_fade(n, s1.ndim)

    # T1 com fade out suave
    t1_out = s1 * fo

    # T2 com pump envelope
    if s2.ndim == 2:
        pump_2d = pump_env[np.newaxis, :]
        t2_pumped = s2 * fi * pump_2d
    else:
        t2_pumped = s2 * fi * pump_env

    out = t1_out + t2_pumped

    peak = np.max(np.abs(out))
    if peak > 1.0:
        out /= peak
    return out
