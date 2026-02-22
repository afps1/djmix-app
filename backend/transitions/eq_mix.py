"""
Transição: EQ Mix — mix estilo DJM-900 com 3 bandas.

Cada banda usa equal-power crossfade (cos²/sin²) pra garantir
energia constante, mas com timing diferente:
- Highs: T2 entra cedo (anticipation), swap em 5%→55%
- Mids: gradual ao longo de toda a transição, 0%→100%
- Bass: swap concentrado, 15%→50% (bass swap rápido)

O timing é calibrado pra evitar vale de energia no início:
- Highs não entram muito cedo (evita pico artificial em Q1)
- Bass swap começa antes e é mais rápido (T2 assume bass logo)
- Resultado: curva de energia mais uniforme entre Q1 e Q2
"""

import numpy as np
from transitions._utils import split_bands

NAME = "eq_mix"
LABEL = "EQ Mix (estilo DJ)"
DESCRIPTION = "Mix de 3 bandas estilo Pioneer DJM-900: bass swap + S-curve mids + hi anticipation"


def apply(seg1, seg2, sr=44100, **kwargs):
    n = min(seg1.shape[-1], seg2.shape[-1])
    s1 = seg1[..., :n]
    s2 = seg2[..., :n]
    lo1, mid1, hi1 = split_bands(s1, sr)
    lo2, mid2, hi2 = split_bands(s2, sr)

    t = np.linspace(0.0, 1.0, n)
    if s1.ndim == 2:
        t = t[np.newaxis, :]

    # ── Highs: T2 entra com leve delay (anticipation suave) ──
    # Equal-power crossfade em 5% → 55%
    # Delay de 5% evita o pico artificial de ter T1 bass + T2 highs juntos no Q1
    hi_t = np.clip((t - 0.05) / 0.50, 0.0, 1.0)
    hi_out = np.cos(hi_t * np.pi * 0.5) ** 2
    hi_in = np.sin(hi_t * np.pi * 0.5) ** 2

    # ── Mids: gradual por toda a transição ──
    # Equal-power crossfade completo 0% → 100%
    mid_out = np.cos(t * np.pi * 0.5) ** 2
    mid_in = np.sin(t * np.pi * 0.5) ** 2

    # ── Bass: swap concentrado e mais cedo ──
    # Equal-power crossfade comprimido em 15% → 50%
    # Começa antes (15% vs 25%) e termina mais cedo (50% vs 65%)
    # Janela de 35% (vs 40%) → swap mais rápido, menos tempo no vale
    bass_t = np.clip((t - 0.15) / 0.35, 0.0, 1.0)
    bass_out = np.cos(bass_t * np.pi * 0.5) ** 2
    bass_in = np.sin(bass_t * np.pi * 0.5) ** 2

    mixed = (lo1 * bass_out + lo2 * bass_in +
             mid1 * mid_out + mid2 * mid_in +
             hi1 * hi_out + hi2 * hi_in)

    # Soft limiter
    peak = np.max(np.abs(mixed))
    if peak > 1.0:
        mixed = np.tanh(mixed / peak) * peak * 0.95
    return mixed
