"""
Sub Boom — impacto grave no final da transicao.

80% de silencio seguido de um boom grave (sine 45Hz com decay exponencial).
Marca o momento exato da entrada da nova track.
"""

import numpy as np
from effects._utils import make_envelope, ensure_stereo, normalize_peak

NAME = "sub_boom"
LABEL = "Sub Boom"
DESCRIPTION = "Impacto grave no final da transicao"


def generate(duration_samples, sr, **kwargs):
    """Gera sub boom stereo (2, samples)."""
    n = duration_samples
    out = np.zeros(n)

    # Onset: 80% da duracao
    onset = int(n * 0.80)
    boom_len = n - onset
    if boom_len < int(0.05 * sr):
        # Duracao muito curta, ajustar
        onset = max(0, n - int(0.3 * sr))
        boom_len = n - onset

    if boom_len > 0:
        t = np.linspace(0, boom_len / sr, boom_len, endpoint=False)

        # Sine 45Hz com decay exponencial
        freq = 45.0
        decay_rate = 6.0  # decay em ~500ms
        boom = np.sin(2 * np.pi * freq * t) * np.exp(-t * decay_rate)

        # Componente de impacto mais agudo (click transiente)
        click_len = min(int(0.008 * sr), boom_len)  # 8ms
        if click_len > 0:
            click = np.sin(2 * np.pi * 120 * t[:click_len]) * np.exp(-t[:click_len] * 80)
            boom[:click_len] += click * 0.4

        # Attack suave pra evitar click (2ms)
        att = min(int(0.002 * sr), boom_len)
        if att > 0:
            boom[:att] *= np.linspace(0, 1, att)

        out[onset:] = boom

    # Sub-rumble crescente antes do boom (ultimos 30% antes do onset)
    rumble_start = max(0, onset - int(n * 0.30))
    rumble_len = onset - rumble_start
    if rumble_len > int(0.1 * sr):
        t_rumble = np.linspace(0, rumble_len / sr, rumble_len, endpoint=False)
        # Ruido filtrado em sub-bass crescente
        rumble = np.sin(2 * np.pi * 35 * t_rumble) * 0.15
        rumble_env = np.linspace(0, 0.6, rumble_len) ** 2
        out[rumble_start:onset] += rumble * rumble_env

    out = normalize_peak(out, 0.9)
    return ensure_stereo(out)
