"""Transição: Cut — corte direto sincronizado ao beat com micro-crossfade."""

import numpy as np

NAME = "cut"
LABEL = "Cut"
DESCRIPTION = "Corte direto sincronizado ao beat com micro-crossfade de 30ms"


def apply(seg1, seg2, sr=44100, **kwargs):
    bpm = kwargs.get("bpm", 128.0)
    n = min(seg1.shape[-1], seg2.shape[-1])

    # Snap do ponto de corte ao beat mais próximo do meio
    beat_samples = int(60.0 / bpm * sr)
    mid = n // 2
    if beat_samples > 0:
        # Achar o beat mais perto do meio
        cut_point = round(mid / beat_samples) * beat_samples
        cut_point = max(beat_samples, min(cut_point, n - beat_samples))
    else:
        cut_point = mid

    # Micro-crossfade de 30ms no ponto de corte (evita click)
    xfade_samples = min(int(0.030 * sr), cut_point, n - cut_point)

    if seg1.ndim == 2:
        out = np.zeros((seg1.shape[0], n))
    else:
        out = np.zeros(n)

    # T1 até o ponto de corte
    out[..., :cut_point] = seg1[..., :cut_point]

    # T2 depois do ponto de corte
    out[..., cut_point:] = seg2[..., cut_point:n]

    # Micro-crossfade na zona de corte
    if xfade_samples > 1:
        xf_start = cut_point - xfade_samples // 2
        xf_end = xf_start + xfade_samples
        xf_start = max(0, xf_start)
        xf_end = min(n, xf_end)
        xf_len = xf_end - xf_start

        fade_out = np.linspace(1.0, 0.0, xf_len)
        fade_in = np.linspace(0.0, 1.0, xf_len)
        if seg1.ndim == 2:
            fade_out = fade_out[np.newaxis, :]
            fade_in = fade_in[np.newaxis, :]

        out[..., xf_start:xf_end] = (
            seg1[..., xf_start:xf_end] * fade_out +
            seg2[..., xf_start:xf_end] * fade_in
        )

    return out
