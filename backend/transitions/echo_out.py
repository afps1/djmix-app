"""Transição: Echo Out — echo/delay na track 1 com fade pra track 2."""

import numpy as np
from transitions._utils import make_fade

NAME = "echo_out"
LABEL = "Echo Out"
DESCRIPTION = "Echo/delay na track de saída com fade pra track de entrada"


def apply(seg1, seg2, sr=44100, **kwargs):
    bpm = kwargs.get("bpm", 120.0)
    n = min(seg1.shape[-1], seg2.shape[-1])
    delay = int(60.0 / bpm * sr * 0.5)
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]
    echoed = s1.copy()
    for tap in range(1, 5):
        offset = tap * delay
        decay = 0.5 ** tap
        if offset < n:
            echoed[..., offset:] += s1[..., :n - offset] * decay
    peak = np.max(np.abs(echoed))
    if peak > 1.0:
        echoed /= peak
    fo, fi = make_fade(n, seg1.ndim)
    return echoed * fo + s2 * fi
