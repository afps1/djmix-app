"""Transição: Tape Stop — simula um deck parando (pitch cai, áudio desacelera)."""

import numpy as np
from transitions._utils import make_fade

NAME = "tape_stop"
LABEL = "Tape Stop"
DESCRIPTION = "Simula deck/tape parando: track 1 desacelera e desce o pitch, track 2 entra"


def apply(seg1, seg2, sr=44100, **kwargs):
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]

    # Tape stop na primeira metade da transição
    stop_end = int(n * 0.5)

    # Gerar o efeito de desaceleração
    # Curva de velocidade: começa em 1.0x, termina em 0.05x (quase parado)
    # Usando curva exponencial pra soar mais natural
    num_chunks = 40
    chunk_size = stop_end // num_chunks
    slowed_chunks = []
    read_pos = 0  # posição de leitura no áudio original

    for i in range(num_chunks):
        # Taxa de velocidade decai exponencialmente
        progress = i / num_chunks
        speed = max(0.05, 1.0 - progress ** 1.8 * 0.95)

        # Quantos samples originais esse chunk consome
        orig_samples = max(1, int(chunk_size * speed))
        end_pos = min(read_pos + orig_samples, s1.shape[-1])
        chunk = s1[..., read_pos:end_pos]

        if chunk.shape[-1] == 0:
            break

        # Reamostrar (esticar pra chunk_size = desacelerar)
        target_len = chunk_size
        if chunk.shape[-1] != target_len and chunk.shape[-1] > 0:
            indices = np.linspace(0, chunk.shape[-1] - 1, target_len).astype(int)
            if chunk.ndim == 2:
                chunk = chunk[:, indices]
            else:
                chunk = chunk[indices]

        slowed_chunks.append(chunk)
        read_pos = end_pos

    # Concatenar chunks desacelerados
    if slowed_chunks[0].ndim == 2:
        stopped = np.concatenate(slowed_chunks, axis=1)
    else:
        stopped = np.concatenate(slowed_chunks)

    stopped_len = stopped.shape[-1]

    # Fade out no tape stop
    fo = np.linspace(1.0, 0.0, stopped_len) ** 2
    if stopped.ndim == 2:
        fo = fo[np.newaxis, :]
    stopped = stopped * fo

    # Montar output
    if s1.ndim == 2:
        out = np.zeros((s1.shape[0], n))
    else:
        out = np.zeros(n)

    # Tape stop no início
    actual_len = min(stopped_len, n)
    out[..., :actual_len] = stopped[..., :actual_len]

    # Track 2 entra com fade suave a partir de ~35%
    t2_start = int(n * 0.35)
    t2_len = n - t2_start
    fi = np.linspace(0.0, 1.0, t2_len) ** 0.5  # fade in rápido
    if s2.ndim == 2:
        fi = fi[np.newaxis, :]
    out[..., t2_start:] += s2[..., t2_start:] * fi

    peak = np.max(np.abs(out))
    if peak > 1.0:
        out /= peak
    return out
