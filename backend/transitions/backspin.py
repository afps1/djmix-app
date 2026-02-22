"""Transição: Backspin — simula puxar o disco pra trás antes de cortar pra track 2."""

import numpy as np
from transitions._utils import make_fade

NAME = "backspin"
LABEL = "Backspin"
DESCRIPTION = "Simula backspin de vinil: track 1 reverte e acelera, depois corta pra track 2"


def apply(seg1, seg2, sr=44100, **kwargs):
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]

    # ── Fase 1 (0–20%): T1 toca normal com fade out suave ──
    normal_end = int(n * 0.20)

    # ── Fase 2 (15%–65%): backspin (T1 reverso com aceleração) ──
    # Usar interpolação pra preencher exatamente o espaço alocado
    spin_start = int(n * 0.15)
    spin_end = int(n * 0.65)
    spin_len = spin_end - spin_start

    # Pegar um trecho de T1 pra reverter (usa a parte tocada até agora)
    source_len = min(int(n * 0.5), s1.shape[-1])
    source = s1[..., :source_len]

    # Reverter
    if source.ndim == 2:
        reversed_src = source[:, ::-1].copy()
    else:
        reversed_src = source[::-1].copy()

    # Gerar posições de leitura com aceleração progressiva
    # Velocidade vai de 1.0x a 3.0x — interpolação cobre todo spin_len
    t = np.linspace(0, 1, spin_len)
    # Integral de velocidade(t) = posição. Velocidade = 1 + 2*t → posição = t + t²
    read_positions = t + t ** 2  # posição normalizada 0→2
    read_positions = read_positions / read_positions[-1]  # normalizar pra 0→1
    read_indices = (read_positions * (reversed_src.shape[-1] - 1)).astype(int)
    read_indices = np.clip(read_indices, 0, reversed_src.shape[-1] - 1)

    if reversed_src.ndim == 2:
        spin_audio = reversed_src[:, read_indices]
    else:
        spin_audio = reversed_src[read_indices]

    # Fade envelope pro backspin: sobe rápido, desce gradual
    spin_env = np.ones(spin_len)
    # Attack (primeiros 10% do spin)
    att = int(spin_len * 0.10)
    spin_env[:att] = np.linspace(0, 1, att)
    # Decay (últimos 40% do spin)
    dec_start = int(spin_len * 0.60)
    dec_len = spin_len - dec_start
    spin_env[dec_start:] = np.linspace(1, 0, dec_len) ** 1.5

    if spin_audio.ndim == 2:
        spin_env = spin_env[np.newaxis, :]
    spin_audio = spin_audio * spin_env

    # ── Fase 3 (20%–100%): T2 fade in ──
    t2_start = int(n * 0.20)

    # ── Montar output ──
    if s1.ndim == 2:
        out = np.zeros((s1.shape[0], n))
    else:
        out = np.zeros(n)

    # T1 normal no início com fade
    normal_fade = np.linspace(1.0, 0.3, normal_end)
    if s1.ndim == 2:
        normal_fade = normal_fade[np.newaxis, :]
    out[..., :normal_end] = s1[..., :normal_end] * normal_fade

    # Backspin
    out[..., spin_start:spin_end] += spin_audio

    # T2 fade in (curva suave que garante som contínuo)
    t2_len = n - t2_start
    fi = np.linspace(0.0, 1.0, t2_len) ** 0.6
    if s2.ndim == 2:
        fi = fi[np.newaxis, :]
    out[..., t2_start:] += s2[..., t2_start:] * fi

    # Limitar pico
    peak = np.max(np.abs(out))
    if peak > 1.0:
        out /= peak
    return out
