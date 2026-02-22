"""Transição: Crossfade — equal-power crossfade entre duas tracks."""

from transitions._utils import make_fade

NAME = "crossfade"
LABEL = "Crossfade"
DESCRIPTION = "Equal-power crossfade entre as duas tracks"


def apply(seg1, seg2, sr=44100, **kwargs):
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]
    fo, fi = make_fade(n, seg1.ndim)
    return s1 * fo + s2 * fi
