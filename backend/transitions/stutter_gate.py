"""Transição: Stutter Gate — gate rítmico sincronizado com BPM, intercala T1 e T2."""

import numpy as np

NAME = "stutter_gate"
LABEL = "Stutter Gate"
DESCRIPTION = "Gate rítmico sincronizado ao BPM: fatias alternadas entre as duas tracks"


def apply(seg1, seg2, sr=44100, **kwargs):
    bpm = kwargs.get("bpm", 128.0)
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]

    # Tamanho de cada "gate slice" = 1/4 de beat (semicolcheia)
    beat_samples = int(60.0 / bpm * sr)
    slice_samples = max(1, beat_samples // 4)

    # Micro-fade pra evitar clicks (2ms)
    micro_fade = int(0.002 * sr)

    if s1.ndim == 2:
        out = np.zeros((s1.shape[0], n))
    else:
        out = np.zeros(n)

    pos = 0
    slice_idx = 0

    while pos < n:
        end = min(pos + slice_samples, n)
        length = end - pos
        progress = pos / n  # 0 → 1 ao longo da transição

        # Probabilidade de tocar T2 aumenta com o progresso
        # Começa 0% T2, termina 100% T2
        # Usa um padrão rítmico: a cada grupo de 4 slices, mais slices são T2
        group_pos = slice_idx % 4
        t2_threshold = progress

        # Padrão rítmico: slices ímpares tendem a mudar antes
        if group_pos in (1, 3):
            use_t2 = progress > 0.3
        elif group_pos == 2:
            use_t2 = progress > 0.5
        else:
            use_t2 = progress > 0.7

        # Nos extremos, forçar
        if progress < 0.1:
            use_t2 = False
        elif progress > 0.9:
            use_t2 = True

        # Selecionar source
        source = s2 if use_t2 else s1
        gate_slice = source[..., pos:end].copy()

        # Aplicar micro-fade nas bordas pra evitar clicks
        if length > micro_fade * 2:
            fade_in = np.linspace(0.0, 1.0, micro_fade)
            fade_out = np.linspace(1.0, 0.0, micro_fade)
            if gate_slice.ndim == 2:
                fade_in = fade_in[np.newaxis, :]
                fade_out = fade_out[np.newaxis, :]
            gate_slice[..., :micro_fade] *= fade_in
            gate_slice[..., -micro_fade:] *= fade_out

        out[..., pos:end] = gate_slice

        pos = end
        slice_idx += 1

    peak = np.max(np.abs(out))
    if peak > 1.0:
        out /= peak
    return out
