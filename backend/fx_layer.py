"""
FX Layer — gera e mixa efeitos de transicao.

Funcoes:
- generate_fx(effect_name, duration_samples, sr) -> numpy array ou None
- mix_fx_layer(mixed_audio, fx_audio, volume_db) -> numpy array
"""

import numpy as np


def generate_fx(effect_name, duration_samples, sr):
    """
    Gera efeito de transicao via plugin system.

    effect_name: nome do efeito (ex: "noise_riser")
    duration_samples: quantos samples a transicao tem
    sr: sample rate

    Returns: numpy array (2, samples) stereo, ou None se efeito nao existe
    """
    from effects import get_effect

    effect_mod = get_effect(effect_name)
    if effect_mod is None:
        return None

    try:
        fx_audio = effect_mod.generate(duration_samples, sr)
        # Garantir stereo (2, samples)
        if fx_audio.ndim == 1:
            fx_audio = np.stack([fx_audio, fx_audio])
        # Garantir tamanho exato
        if fx_audio.shape[-1] > duration_samples:
            fx_audio = fx_audio[:, :duration_samples]
        elif fx_audio.shape[-1] < duration_samples:
            pad = duration_samples - fx_audio.shape[-1]
            fx_audio = np.pad(fx_audio, ((0, 0), (0, pad)))
        return fx_audio
    except Exception as e:
        print(f"[fx_layer] Erro ao gerar efeito '{effect_name}': {e}")
        return None


def mix_fx_layer(mixed_audio, fx_audio, volume_db=-12.0):
    """
    Mixa o FX layer por baixo do audio da transicao.

    mixed_audio: audio da transicao (2, samples) ou (samples,)
    fx_audio: efeito gerado (2, samples)
    volume_db: volume do FX em dB (default -12dB)

    Returns: audio mixado, mesmo shape do input

    Usa soft clip pra tratar picos sem reduzir o volume da musica.
    Apenas as amostras acima de 0.85 sao comprimidas suavemente
    via tanh, preservando o volume percebido da musica intacto.
    """
    # Converter dB pra ganho linear
    gain = 10.0 ** (volume_db / 20.0)

    # Ajustar shapes se necessario
    if mixed_audio.ndim == 1 and fx_audio.ndim == 2:
        # Mono mix + stereo FX -> usar mono do FX
        fx_mono = np.mean(fx_audio, axis=0)
        out = mixed_audio + fx_mono * gain
    elif mixed_audio.ndim == 2 and fx_audio.ndim == 1:
        # Stereo mix + mono FX -> expandir FX
        fx_stereo = np.stack([fx_audio, fx_audio])
        out = mixed_audio + fx_stereo * gain
    else:
        out = mixed_audio + fx_audio * gain

    # Igualar tamanhos (safety)
    min_n = min(out.shape[-1], mixed_audio.shape[-1])
    if mixed_audio.ndim == 2:
        out = out[:, :min_n]
    else:
        out = out[:min_n]

    # Soft clip: comprimir apenas os picos acima do threshold,
    # preservando o volume da musica intacto.
    threshold = 0.85
    ceiling = 0.95
    headroom = ceiling - threshold
    abs_out = np.abs(out)
    above = abs_out > threshold
    if np.any(above):
        sign = np.sign(out)
        excess = abs_out - threshold
        compressed = threshold + headroom * np.tanh(excess / headroom)
        out = np.where(above, sign * compressed, out)

    return out
