"""
DJMIX Engine — v3.1 (module version)

Refactored from djmix.py for use as importable backend engine.
All functions accept parameters and return data structures.
Print replaced by optional progress_callback.
"""

import numpy as np
import librosa
import soundfile as sf
import pyloudnorm as pyln
from scipy.ndimage import uniform_filter1d
import os, warnings, uuid, time
warnings.filterwarnings("ignore")

from transitions import TRANSITIONS, TRANSITION_LIST, get_transition
from fx_layer import generate_fx, mix_fx_layer


# ─────────────────────────────────────────
# AUDIO UTILS
# ─────────────────────────────────────────

def to_mono(y):
    if y.ndim == 2:
        return librosa.to_mono(y)
    return y

def n_samples(y):
    return y.shape[-1]

def audio_slice(y, start, end):
    start = max(0, int(start))
    end = max(start, int(end))
    if y.ndim == 2:
        return y[:, start:end]
    return y[start:end]

def audio_pad(y, pad_width):
    if pad_width <= 0:
        return y
    if y.ndim == 2:
        return np.pad(y, ((0, 0), (0, pad_width)))
    return np.pad(y, (0, pad_width))

def audio_concat(arrays):
    arrays = [a for a in arrays if n_samples(a) > 0]
    if not arrays:
        return np.zeros(0)
    if arrays[0].ndim == 2:
        return np.concatenate(arrays, axis=1)
    return np.concatenate(arrays)

def ensure_stereo(y):
    if y.ndim == 1:
        return np.stack([y, y])
    return y


def crossfade_junction(seg_a, seg_b, xfade_ms=30, sr=44100):
    """
    Aplica micro-crossfade na junção entre dois segmentos.
    Os últimos xfade_ms de seg_a são crossfadados com os primeiros xfade_ms de seg_b.
    Retorna (seg_a_trimmed, seg_b_trimmed) onde a zona de overlap vira um segmento fundido
    no final de seg_a, e seg_b começa após o crossfade.
    """
    xfade_samp = min(int(xfade_ms / 1000 * sr), n_samples(seg_a), n_samples(seg_b))
    if xfade_samp < 2:
        return seg_a, seg_b

    # Fade curves (equal-power)
    t = np.linspace(0.0, 1.0, xfade_samp)
    fade_out = np.cos(t * np.pi * 0.5) ** 2  # 1→0
    fade_in = np.sin(t * np.pi * 0.5) ** 2   # 0→1
    if seg_a.ndim == 2:
        fade_out = fade_out[np.newaxis, :]
        fade_in = fade_in[np.newaxis, :]

    # Zona de crossfade: final de A + início de B
    tail_a = audio_slice(seg_a, n_samples(seg_a) - xfade_samp, n_samples(seg_a))
    head_b = audio_slice(seg_b, 0, xfade_samp)
    blended = tail_a * fade_out + head_b * fade_in

    # Remontar: seg_a sem tail + blended + seg_b sem head
    a_trimmed = audio_slice(seg_a, 0, n_samples(seg_a) - xfade_samp)
    b_trimmed = audio_slice(seg_b, xfade_samp, n_samples(seg_b))

    return audio_concat([a_trimmed, blended]), b_trimmed


# ─────────────────────────────────────────
# LUFS LOUDNESS
# ─────────────────────────────────────────

def measure_lufs(audio, sr):
    """Mede loudness integrada em LUFS (ITU-R BS.1770-4)."""
    meter = pyln.Meter(sr)
    # pyloudnorm espera (samples, channels), engine usa (channels, samples)
    if audio.ndim == 2:
        data = audio.T
    else:
        data = audio
    try:
        return meter.integrated_loudness(data)
    except Exception:
        return float('-inf')


def normalize_lufs(audio, sr, target_lufs=-14.0):
    """Normaliza áudio para target LUFS. Limita pico a 0.95 pra evitar clipping."""
    current_lufs = measure_lufs(audio, sr)
    if current_lufs == float('-inf') or np.isinf(current_lufs):
        return audio
    # pyloudnorm espera (samples, channels)
    if audio.ndim == 2:
        data = audio.T
        normalized = pyln.normalize.loudness(data, current_lufs, target_lufs)
        normalized = normalized.T  # volta pra (channels, samples)
    else:
        normalized = pyln.normalize.loudness(audio, current_lufs, target_lufs)
    # Limitar pico pra evitar clipping
    peak = np.max(np.abs(normalized))
    if peak > 0.95:
        normalized = normalized * (0.95 / peak)
    return normalized


# ─────────────────────────────────────────
# KEY DETECTION (Camelot Wheel)
# ─────────────────────────────────────────

# Perfis Krumhansl-Schmuckler (correlação com chroma pra detectar tonalidade)
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Nomes das notas (0=C, 1=C#, ..., 11=B)
_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Mapeamento tonalidade → código Camelot
# Major keys (B suffix)
_CAMELOT_MAJOR = {
    'C': '8B', 'C#': '3B', 'D': '10B', 'D#': '5B', 'E': '12B', 'F': '7B',
    'F#': '2B', 'G': '9B', 'G#': '4B', 'A': '11B', 'A#': '6B', 'B': '1B',
}
# Minor keys (A suffix)
_CAMELOT_MINOR = {
    'C': '5A', 'C#': '12A', 'D': '7A', 'D#': '2A', 'E': '9A', 'F': '4A',
    'F#': '11A', 'G': '6A', 'G#': '1A', 'A': '8A', 'A#': '3A', 'B': '10A',
}


def detect_key(y, sr):
    """
    Detecta tonalidade usando chroma features + algoritmo Krumhansl-Schmuckler.
    Retorna dict com key (ex: 'C major'), camelot (ex: '8B'), root, mode.
    """
    y_mono = to_mono(y)
    # Usar chroma_cqt pra melhor resolução em frequências musicais
    chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr)
    # Média temporal → perfil de 12 notas
    chroma_avg = np.mean(chroma, axis=1)

    best_corr = -np.inf
    best_key = None
    best_mode = None

    for shift in range(12):
        # Rotaciona perfil pra testar cada tonalidade
        profile_major = np.roll(_KS_MAJOR, shift)
        profile_minor = np.roll(_KS_MINOR, shift)

        corr_major = np.corrcoef(chroma_avg, profile_major)[0, 1]
        corr_minor = np.corrcoef(chroma_avg, profile_minor)[0, 1]

        if corr_major > best_corr:
            best_corr = corr_major
            best_key = _NOTE_NAMES[shift]
            best_mode = 'major'
        if corr_minor > best_corr:
            best_corr = corr_minor
            best_key = _NOTE_NAMES[shift]
            best_mode = 'minor'

    # Mapeamento pra Camelot
    if best_mode == 'major':
        camelot = _CAMELOT_MAJOR.get(best_key, '?')
    else:
        camelot = _CAMELOT_MINOR.get(best_key, '?')

    return {
        "key": f"{best_key} {best_mode}",
        "camelot": camelot,
        "root": best_key,
        "mode": best_mode,
    }


# ─────────────────────────────────────────
# BPM / BEAT DETECTION
# ─────────────────────────────────────────

def detect_bpm(y, sr):
    y_mono = to_mono(y)
    tempo1, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
    tempo1 = float(np.atleast_1d(tempo1)[0])

    onset_env = librosa.onset.onset_strength(y=y_mono, sr=sr)
    tempo2 = float(np.atleast_1d(
        librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)[0]
    )[0])

    ac = librosa.autocorrelate(onset_env, max_size=sr // 512 * 4)
    ac = ac[sr // 512 // 4:]
    if len(ac) > 0:
        peak = np.argmax(ac)
        lag_sec = (peak + sr // 512 // 4) * 512 / sr
        tempo3 = 60.0 / lag_sec if lag_sec > 0 else tempo1
    else:
        tempo3 = tempo1

    candidates = sorted([tempo1, tempo2, tempo3])
    return {
        "bpm": candidates[1],
        "candidates": [tempo1, tempo2, tempo3],
    }


def get_beats(y, sr):
    y_mono = to_mono(y)
    _, beat_frames = librosa.beat.beat_track(y=y_mono, sr=sr)
    return librosa.frames_to_time(beat_frames, sr=sr)


def fit_beat_grid(beat_times, bpm):
    if len(beat_times) < 2:
        return beat_times[0] if len(beat_times) else 0.0, 60.0 / bpm
    expected_interval = 60.0 / bpm
    indices = np.round((beat_times - beat_times[0]) / expected_interval).astype(int)
    A = np.vstack([indices, np.ones(len(indices))]).T
    result = np.linalg.lstsq(A, beat_times, rcond=None)
    interval, phase = result[0]
    return phase, interval


def snap_to_beat(time_sec, beats):
    if len(beats) == 0:
        return time_sec
    idx = np.argmin(np.abs(beats - time_sec))
    return float(beats[idx])


# ─────────────────────────────────────────
# ENERGY / CUE DETECTION
# ─────────────────────────────────────────

def compute_energy_profile(y, sr, hop=512, smooth_sec=2.0):
    y_mono = to_mono(y)
    rms = librosa.feature.rms(y=y_mono, hop_length=hop)[0]
    smooth_frames = max(1, int(smooth_sec * sr / hop))
    rms_smooth = uniform_filter1d(rms, size=smooth_frames)
    times = librosa.frames_to_time(np.arange(len(rms_smooth)), sr=sr, hop_length=hop)
    peak = np.max(rms_smooth)
    if peak > 0:
        rms_smooth = rms_smooth / peak
    return rms_smooth, times


def find_drops(energy, times, threshold=0.5, min_gap_sec=8.0):
    above = energy > threshold
    drops = []
    was_below = True
    for i in range(1, len(above)):
        if above[i] and was_below:
            if not drops or (times[i] - drops[-1]) > min_gap_sec:
                drops.append(float(times[i]))
        was_below = not above[i]
    return drops


def find_breakdowns(energy, times, threshold=0.35, min_duration_sec=4.0, min_gap_sec=16.0):
    below = energy < threshold
    breakdowns = []
    in_bd = False
    start_idx = 0

    for i in range(len(below)):
        if below[i] and not in_bd:
            in_bd = True
            start_idx = i
        elif not below[i] and in_bd:
            in_bd = False
            duration = times[i] - times[start_idx]
            if duration >= min_duration_sec:
                if not breakdowns or (times[start_idx] - breakdowns[-1]["end"]) > min_gap_sec:
                    breakdowns.append({
                        "start": float(times[start_idx]),
                        "end": float(times[i]),
                        "energy": float(np.mean(energy[start_idx:i])),
                    })

    if in_bd:
        duration = times[-1] - times[start_idx]
        if duration >= min_duration_sec:
            breakdowns.append({
                "start": float(times[start_idx]),
                "end": float(times[-1]),
                "energy": float(np.mean(energy[start_idx:])),
            })

    return breakdowns


def detect_cue_in(y, sr, beats, strategy="first_drop", search_pct=0.4):
    duration = n_samples(y) / sr
    search_end = duration * search_pct
    energy, e_times = compute_energy_profile(y, sr)

    if strategy == "first_drop":
        drops = find_drops(energy, e_times)
        drops_in_range = [d for d in drops if d < search_end]
        if drops_in_range:
            return snap_to_beat(drops_in_range[0], beats), "first_drop"

    if strategy in ("first_drop", "energy_rise"):
        for e, t in zip(energy, e_times):
            if t > search_end:
                break
            if e > 0.4:
                return snap_to_beat(t, beats), "energy_rise"

    if len(beats) > 0:
        return float(beats[0]), "first_beat"
    return 0.0, "fallback_zero"


def detect_cue_out(y, sr, beats, strategy="last_breakdown", search_pct=0.6):
    duration = n_samples(y) / sr
    search_start = duration * search_pct
    energy, e_times = compute_energy_profile(y, sr)

    if strategy == "last_breakdown":
        breakdowns = find_breakdowns(energy, e_times)
        bds = [b for b in breakdowns if b["start"] >= search_start]
        if bds:
            return snap_to_beat(bds[-1]["start"], beats), "last_breakdown"

    if strategy in ("last_breakdown", "energy_drop"):
        mask = e_times >= search_start
        e_zone = energy[mask]
        t_zone = e_times[mask]
        if len(e_zone) > 10:
            diff = np.diff(e_zone)
            biggest = np.argmin(diff)
            if diff[biggest] < -0.1:
                return snap_to_beat(t_zone[biggest], beats), "energy_drop"

    cue = duration * 0.75
    return snap_to_beat(cue, beats), "fallback_75pct"


# ─────────────────────────────────────────
# FULL TRACK ANALYSIS
# ─────────────────────────────────────────

def analyze_track(filepath):
    """
    Analisa uma track completa.
    Retorna dict com: y, sr, bpm, beats, cue_in, cue_out, energy, drops, breakdowns, etc.
    """
    y, sr = librosa.load(filepath, sr=None, mono=False)
    channels = y.shape[0] if y.ndim == 2 else 1
    duration = n_samples(y) / sr

    bpm_info = detect_bpm(y, sr)
    bpm = bpm_info["bpm"]
    beats = get_beats(y, sr)

    auto_cue_in, cue_in_method = detect_cue_in(y, sr, beats)
    auto_cue_out, cue_out_method = detect_cue_out(y, sr, beats)

    energy, e_times = compute_energy_profile(y, sr)
    drops = find_drops(energy, e_times)
    breakdowns = find_breakdowns(energy, e_times)

    # Loudness LUFS
    lufs = measure_lufs(y, sr)

    # Key detection (Camelot)
    key_info = detect_key(y, sr)

    # Downsample energy pra enviar ao frontend (1 ponto por ~50ms)
    target_points = int(duration * 20)  # 20 pontos por segundo
    if len(energy) > target_points:
        indices = np.linspace(0, len(energy) - 1, target_points).astype(int)
        energy_ds = energy[indices].tolist()
        e_times_ds = e_times[indices].tolist()
    else:
        energy_ds = energy.tolist()
        e_times_ds = e_times.tolist()

    return {
        # Audio data (não serializado pra JSON)
        "y": y,
        "sr": sr,
        # Metadata (serializável)
        "channels": channels,
        "duration": round(duration, 3),
        "bpm": round(bpm, 3),
        "bpm_candidates": [round(c, 2) for c in bpm_info["candidates"]],
        "beats": [round(b, 4) for b in beats.tolist()],
        "auto_cue_in": round(auto_cue_in, 3),
        "auto_cue_out": round(auto_cue_out, 3),
        "cue_in_method": cue_in_method,
        "cue_out_method": cue_out_method,
        "drops": drops,
        "breakdowns": breakdowns,
        "energy": energy_ds,
        "energy_times": e_times_ds,
        "lufs": round(lufs, 1) if not np.isinf(lufs) else None,
        "key": key_info["key"],
        "camelot": key_info["camelot"],
    }


# ─────────────────────────────────────────
# TIME-STRETCH
# ─────────────────────────────────────────

def time_stretch_audio(y, sr, src_bpm, dst_bpm):
    if abs(src_bpm - dst_bpm) < 0.5:
        return y
    ratio = dst_bpm / src_bpm
    if y.ndim == 2:
        channels = []
        for ch in range(y.shape[0]):
            stretched = librosa.effects.time_stretch(y[ch], rate=ratio)
            channels.append(stretched)
        min_len = min(c.shape[0] for c in channels)
        channels = [c[:min_len] for c in channels]
        result = np.stack(channels)
    else:
        result = librosa.effects.time_stretch(y, rate=ratio)
    # Peak limiting: time stretch pode gerar picos acima de 1.0
    peak = np.max(np.abs(result))
    if peak > 0.95:
        result = result * (0.95 / peak)
    return result


# ─────────────────────────────────────────
# PHASE ALIGNMENT
# ─────────────────────────────────────────

def phase_align(beat_times_1, beat_times_2, start1, start2, bpm, bpm1=None):
    """
    Alinha a fase de T2 pra casar com T1 (possivelmente após time stretch).

    bpm:  BPM alvo (= align_bpm, geralmente bpm2 em gradual mode)
    bpm1: BPM original de T1 antes do stretch.
          Se None ou == bpm, assume que T1 já está no BPM alvo.

    Quando T1 é esticado de bpm1 → bpm, as posições dos beats escalam
    pelo fator bpm1/bpm. Essa correção é essencial pra calcular a fase
    correta no domínio esticado.
    """
    bpm1 = bpm1 or bpm
    beat_interval = 60.0 / bpm  # intervalo alvo (após stretch)
    bt1 = beat_times_1 - start1
    bt2 = beat_times_2 - start2

    bt1_valid = bt1[bt1 >= 0]
    bt2_valid = bt2[bt2 >= 0]

    if len(bt1_valid) < 2 or len(bt2_valid) < 2:
        return start2

    # Fit cada track no SEU PRÓPRIO BPM
    phase1, _ = fit_beat_grid(bt1_valid, bpm1)
    phase2, _ = fit_beat_grid(bt2_valid, bpm)

    # Converter fase de T1 pro domínio esticado:
    # Após stretch bpm1 → bpm, posições temporais escalam por bpm1/bpm
    phi1 = (phase1 * bpm1 / bpm) % beat_interval
    phi2 = phase2 % beat_interval

    # delta = quanto avançar start2 pra que T2 beats caiam sobre T1 beats.
    # Avançar start2 = extrair seg_in de posição posterior em y2 =
    # beats aparecem MAIS CEDO no mix. Logo: delta = (phi2 - phi1).
    # (Bug anterior: era (phi1 - phi2) que AFASTAVA os beats em vez de alinhar!)
    delta = (phi2 - phi1) % beat_interval

    if delta > beat_interval / 2:
        delta -= beat_interval

    result = start2 + delta

    # Se o resultado é negativo (cue_in muito perto do início da track),
    # avançar um beat interval pra pegar o próximo beat em vez do anterior.
    # Beats se repetem periodicamente, então a fase continua correta.
    if result < 0:
        result += beat_interval

    return result


def align_and_verify(y1, sr, y2, start1, start2, bpm, transition_sec,
                     bpm1=None, tolerance=20.0, max_iter=5):
    """
    Alinha T2 e verifica iterativamente.

    bpm:  BPM alvo (= align_bpm)
    bpm1: BPM original de T1 (antes do stretch). Se None, = bpm.
          Quando T1 é esticado de bpm1 → bpm, precisamos converter as
          posições dos beats de T1 pro domínio esticado antes de comparar.
    """
    bpm1 = bpm1 or bpm
    stretch_ratio = bpm1 / bpm  # fator de escala temporal (> 1 se T1 mais rápida)
    window = transition_sec + 4

    s1s = max(0, int((start1 - 2) * sr))
    e1s = min(n_samples(y1), int((start1 + window) * sr))
    beats1 = get_beats(audio_slice(y1, s1s, e1s), sr) + (s1s / sr)

    s2s = max(0, int((start2 - 2) * sr))
    e2s = min(n_samples(y2), int((start2 + window) * sr))
    beats2 = get_beats(audio_slice(y2, s2s, e2s), sr) + (s2s / sr)

    start2 = phase_align(beats1, beats2, start1, start2, bpm, bpm1=bpm1)

    beat_interval = 60.0 / bpm  # intervalo alvo (após stretch)
    for _ in range(max_iter):
        s2s = max(0, int((start2 - 2) * sr))
        e2s = min(n_samples(y2), int((start2 + window) * sr))
        beats2 = get_beats(audio_slice(y2, s2s, e2s), sr) + (s2s / sr)

        bt1_rel = beats1 - start1
        bt2_rel = beats2 - start2
        bt1_rel = bt1_rel[(bt1_rel >= 0) & (bt1_rel <= transition_sec)]
        bt2_rel = bt2_rel[(bt2_rel >= 0) & (bt2_rel <= transition_sec)]

        # Converter posições de T1 pro domínio esticado
        # Após stretch bpm1 → bpm, cada posição temporal escala por bpm1/bpm
        bt1_stretched = bt1_rel * stretch_ratio

        if len(bt1_stretched) == 0 or len(bt2_rel) == 0:
            break

        # Erro assinado: positivo = T2 atrasado, negativo = T2 adiantado
        signed_offsets = []
        for b1 in bt1_stretched:
            idx = np.argmin(np.abs(bt2_rel - b1))
            d = bt2_rel[idx] - b1
            if abs(d) * 1000 < beat_interval * 1000 * 0.4:
                signed_offsets.append(d)

        if not signed_offsets:
            break

        mean_err = np.mean(np.abs(signed_offsets)) * 1000  # ms
        if mean_err <= tolerance:
            break

        # Micro-correção direta: avançar start2 pelo offset médio assinado.
        # Se T2 está atrasado (positivo), aumentar start2 faz o segmento
        # começar mais tarde, puxando os beats pra posição correta.
        correction = np.mean(signed_offsets)
        start2 = max(0, start2 + correction)

    return start2


# ─────────────────────────────────────────
# PREVIEW (render a transition snippet)
# ─────────────────────────────────────────

def render_preview(track1_info, track2_info, cue_out_sec, cue_in_sec,
                   transition_type="eq_mix", transition_sec=8,
                   bpm_mode="gradual", context_sec=4,
                   effect=None, effect_volume=-12.0):
    """
    Renderiza preview de uma transição: context antes + transição + context depois.
    Retorna (audio_array, sr).
    """
    y1, sr1 = track1_info["y"], track1_info["sr"]
    y2, sr2 = track2_info["y"], track2_info["sr"]
    bpm1, bpm2 = track1_info["bpm"], track2_info["bpm"]

    # Resample pra SR comum
    sr = max(sr1, sr2)
    if sr1 != sr:
        y1 = librosa.resample(y1, orig_sr=sr1, target_sr=sr)
    if sr2 != sr:
        y2 = librosa.resample(y2, orig_sr=sr2, target_sr=sr)

    # Stereo
    need_stereo = y1.ndim == 2 or y2.ndim == 2
    if need_stereo:
        y1 = ensure_stereo(y1)
        y2 = ensure_stereo(y2)

    trans_dur_samp = int(transition_sec * sr)
    ctx_samp = int(context_sec * sr)

    # Segmentos
    t1_start = int(cue_out_sec * sr)
    seg_pre = audio_slice(y1, max(0, t1_start - ctx_samp), t1_start)
    seg_out = audio_slice(y1, t1_start, min(t1_start + trans_dur_samp, n_samples(y1)))
    if n_samples(seg_out) < trans_dur_samp:
        seg_out = audio_pad(seg_out, trans_dur_samp - n_samples(seg_out))

    t2_start = int(cue_in_sec * sr)
    seg_in = audio_slice(y2, t2_start, min(t2_start + trans_dur_samp, n_samples(y2)))
    if n_samples(seg_in) < trans_dur_samp:
        seg_in = audio_pad(seg_in, trans_dur_samp - n_samples(seg_in))

    # BPM handling
    if bpm_mode == "gradual" and abs(bpm1 - bpm2) > 0.5:
        seg_out = time_stretch_audio(seg_out, sr, bpm1, bpm2)
        if n_samples(seg_out) > n_samples(seg_in):
            seg_out = audio_slice(seg_out, 0, n_samples(seg_in))
        elif n_samples(seg_in) > n_samples(seg_out):
            seg_in = audio_slice(seg_in, 0, n_samples(seg_out))

    # Phase align
    align_bpm = bpm2 if bpm_mode == "gradual" else bpm1
    # Quando gradual, T1 foi esticado de bpm1 → align_bpm (= bpm2).
    # Precisamos informar o bpm1 original pro alinhamento correto.
    src_bpm1 = bpm1 if (bpm_mode == "gradual" and abs(bpm1 - bpm2) > 0.5) else None
    start2_aligned = align_and_verify(
        y1, sr, y2, cue_out_sec, cue_in_sec, align_bpm, transition_sec,
        bpm1=src_bpm1
    )

    # Recalcular seg_in com alinhamento
    t2_aligned = max(0, round(start2_aligned * sr))
    seg_in = audio_slice(y2, t2_aligned, min(t2_aligned + trans_dur_samp, n_samples(y2)))
    if n_samples(seg_in) < trans_dur_samp:
        seg_in = audio_pad(seg_in, trans_dur_samp - n_samples(seg_in))

    # Igualar
    min_n = min(n_samples(seg_out), n_samples(seg_in))
    seg_out = audio_slice(seg_out, 0, min_n)
    seg_in = audio_slice(seg_in, 0, min_n)

    # seg_post: continua de onde seg_in REALMENTE terminou (posição alinhada)
    t2_post_start = t2_aligned + min_n
    seg_post = audio_slice(y2, min(t2_post_start, n_samples(y2)),
                           min(t2_post_start + ctx_samp, n_samples(y2)))

    # Transição
    trans_func = get_transition(transition_type)
    mixed = trans_func(seg_out, seg_in, sr=sr, bpm=align_bpm)

    # FX layer (efeito de transicao)
    fx_audio_diag = None
    if effect:
        fx_audio = generate_fx(effect, n_samples(mixed), sr)
        if fx_audio is not None:
            fx_audio_diag = fx_audio
            mixed = mix_fx_layer(mixed, fx_audio, effect_volume)

    # Micro-crossfade nas junções pra eliminar descontinuidade
    # (split_bands IIR causa diferença de fase entre áudio processado e raw)
    seg_pre, mixed = crossfade_junction(seg_pre, mixed, xfade_ms=30, sr=sr)
    mixed, seg_post = crossfade_junction(mixed, seg_post, xfade_ms=30, sr=sr)

    # Montar preview
    preview = audio_concat([seg_pre, mixed, seg_post])

    # Normalizar loudness do preview
    preview = normalize_lufs(preview, sr)

    # ── LOG DIAGNÓSTICO ──
    _log_preview_diagnostics(
        sr=sr, bpm1=bpm1, bpm2=bpm2, bpm_mode=bpm_mode, align_bpm=align_bpm,
        transition_type=transition_type, transition_sec=transition_sec,
        cue_out_sec=cue_out_sec, cue_in_sec=cue_in_sec,
        t2_start=t2_start, t2_aligned=t2_aligned, min_n=min_n,
        trans_dur_samp=trans_dur_samp,
        seg_pre=seg_pre, seg_out=seg_out, seg_in=seg_in,
        seg_post=seg_post, mixed=mixed, preview=preview,
        effect=effect, effect_volume=effect_volume,
        y1=y1, y2=y2,
        fx_audio=fx_audio_diag,
    )

    return preview, sr


# ─────────────────────────────────────────
# PREVIEW DIAGNOSTICS
# ─────────────────────────────────────────

def _log_preview_diagnostics(*, sr, bpm1, bpm2, bpm_mode, align_bpm,
                              transition_type, transition_sec,
                              cue_out_sec, cue_in_sec,
                              t2_start, t2_aligned, min_n, trans_dur_samp,
                              seg_pre, seg_out, seg_in, seg_post,
                              mixed, preview, effect, effect_volume,
                              y1=None, y2=None, fx_audio=None):
    """Loga informações detalhadas do preview pra diagnóstico de qualidade."""

    def rms(audio):
        """RMS de um segmento."""
        return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))

    def peak(audio):
        return float(np.max(np.abs(audio)))

    def lufs(audio):
        return measure_lufs(audio, sr)

    # Dividir a transição em 4 quartos pra análise de energia
    mixed_mono = mixed[0] if mixed.ndim == 2 else mixed
    quarter = n_samples(mixed) // 4
    q_rms = []
    for q in range(4):
        s = q * quarter
        e = s + quarter if q < 3 else n_samples(mixed)
        q_rms.append(rms(mixed_mono[s:e]))

    # Detectar vale: menor RMS vs média
    min_q = min(q_rms)
    max_q = max(q_rms)
    dip_ratio = min_q / max_q if max_q > 0 else 0

    # Junção mixed→post: diferença de amplitude (~45ms cada lado = 2000 samp)
    junction = n_samples(seg_pre) + n_samples(mixed)
    preview_mono = preview[0] if preview.ndim == 2 else preview
    total_samp = n_samples(preview)
    jwin = 2000  # ~45ms — janela grande o suficiente pra capturar vários ciclos
    if junction > jwin and junction < total_samp - jwin:
        before = rms(preview_mono[junction - jwin:junction])
        after = rms(preview_mono[junction:junction + jwin])
        junction_diff_db = 20 * np.log10(after / before) if before > 0 and after > 0 else 0
    else:
        junction_diff_db = 0.0

    # Beat error: medir erro real de alinhamento entre T1 esticado e T2
    beat_error_ms = None
    if y1 is not None and y2 is not None:
        try:
            stretch_ratio = bpm1 / align_bpm if (bpm_mode == "gradual" and abs(bpm1 - bpm2) > 0.5) else 1.0
            # Detectar beats de T1 na zona de transição
            t1s = max(0, int((cue_out_sec - 1) * sr))
            t1e = min(n_samples(y1), int((cue_out_sec + transition_sec + 2) * sr))
            b1 = get_beats(audio_slice(y1, t1s, t1e), sr) + (t1s / sr)
            # Posições relativas ao cue_out, esticadas pro domínio alvo
            b1_rel = (b1 - cue_out_sec) * stretch_ratio
            b1_rel = b1_rel[(b1_rel >= 0) & (b1_rel <= transition_sec)]

            # Detectar beats de T2 na zona de transição (posição alinhada)
            start2_sec = t2_aligned / sr
            t2s = max(0, int((start2_sec - 1) * sr))
            t2e = min(n_samples(y2), int((start2_sec + transition_sec + 2) * sr))
            b2 = get_beats(audio_slice(y2, t2s, t2e), sr) + (t2s / sr)
            b2_rel = b2 - start2_sec
            b2_rel = b2_rel[(b2_rel >= 0) & (b2_rel <= transition_sec)]

            if len(b1_rel) > 0 and len(b2_rel) > 0:
                errors = []
                for b in b1_rel:
                    idx = np.argmin(np.abs(b2_rel - b))
                    d = abs(b - b2_rel[idx]) * 1000  # ms
                    beat_interval_ms = 60000.0 / align_bpm
                    if d < beat_interval_ms * 0.4:
                        errors.append(d)
                if errors:
                    beat_error_ms = np.mean(errors)
        except Exception:
            pass

    # Phase alignment shift
    phase_shift_ms = (t2_aligned - t2_start) / sr * 1000
    length_diff_samp = trans_dur_samp - min_n

    print("\n" + "=" * 70)
    print("PREVIEW DIAGNOSTICS")
    print("=" * 70)
    print(f"  Transition:    {transition_type} | {transition_sec}s | bpm_mode={bpm_mode}")
    stretch_applied = bpm_mode == "gradual" and abs(bpm1 - bpm2) > 0.5
    stretch_ratio = bpm1 / bpm2 if stretch_applied else 1.0
    print(f"  BPM:           T1={bpm1:.1f} → T2={bpm2:.1f} | align_bpm={align_bpm:.1f}")
    if stretch_applied:
        print(f"  Stretch:       T1 esticado {bpm1:.1f}→{bpm2:.1f} (ratio={stretch_ratio:.4f})")
    print(f"  Cue points:    out={cue_out_sec:.3f}s | in={cue_in_sec:.3f}s")
    print(f"  Effect:        {effect or 'nenhum'}{f' ({effect_volume:.0f} dB)' if effect else ''}")
    print(f"  SR:            {sr} Hz")
    print(f"  ── Phase Alignment ──")
    print(f"  Original t2:   {t2_start} samp ({t2_start/sr:.4f}s)")
    print(f"  Aligned t2:    {t2_aligned} samp ({t2_aligned/sr:.4f}s)")
    print(f"  Shift:         {phase_shift_ms:+.1f} ms ({t2_aligned - t2_start:+d} samp)")
    if stretch_applied:
        print(f"  Stretch corr:  ✓ phase_align usando bpm1={bpm1:.1f} + conversão pro domínio esticado")
    print(f"  ── Segment Lengths ──")
    print(f"  seg_pre:       {n_samples(seg_pre)} ({n_samples(seg_pre)/sr:.3f}s)")
    print(f"  seg_out:       {n_samples(seg_out)} ({n_samples(seg_out)/sr:.3f}s)")
    print(f"  seg_in:        {n_samples(seg_in)} ({n_samples(seg_in)/sr:.3f}s)")
    print(f"  mixed:         {n_samples(mixed)} ({n_samples(mixed)/sr:.3f}s)")
    print(f"  seg_post:      {n_samples(seg_post)} ({n_samples(seg_post)/sr:.3f}s)")
    print(f"  preview total: {total_samp} ({total_samp/sr:.3f}s)")
    print(f"  trans expected:{trans_dur_samp} | actual={min_n} | diff={length_diff_samp} samp")
    print(f"  ── Energy Analysis ──")
    print(f"  seg_out  RMS:  {rms(seg_out):.4f} | peak={peak(seg_out):.4f}")
    print(f"  seg_in   RMS:  {rms(seg_in):.4f} | peak={peak(seg_in):.4f}")
    print(f"  mixed    RMS:  {rms(mixed):.4f} | peak={peak(mixed):.4f}")
    print(f"  preview  LUFS: {lufs(preview):.1f}")
    bar = "█"
    print(f"  Transition energy by quarter:")
    for i, qr in enumerate(q_rms):
        pct = int(qr / max_q * 30) if max_q > 0 else 0
        label = ["0-25%", "25-50%", "50-75%", "75-100%"][i]
        print(f"    Q{i+1} ({label}):  {qr:.4f} {bar * pct}")
    print(f"  Energy dip:    min/max = {dip_ratio:.2f} {'⚠ DIP' if dip_ratio < 0.5 else '✓ OK'}")
    print(f"  ── Junction Quality ──")
    print(f"  mixed→post:    {junction_diff_db:+.1f} dB {'⚠ BREAK' if abs(junction_diff_db) > 6 else '✓ OK'}")
    print(f"  ── Beat Alignment ──")
    if beat_error_ms is not None:
        # Thresholds consideram imprecisão inerente do beat tracker (~20-30ms)
        status = "✓ TIGHT" if beat_error_ms < 25 else ("✓ OK" if beat_error_ms < 50 else "⚠ LARGO")
        print(f"  Mean beat err: {beat_error_ms:.1f} ms {status}")
    else:
        print(f"  Mean beat err: N/A (poucos beats detectados)")

    # FX diagnostics
    if effect and fx_audio is not None:
        print(f"  ── FX Quality ──")
        try:
            fx_rms_val = rms(fx_audio)
            fx_peak_val = peak(fx_audio)
            gain_linear = 10.0 ** (effect_volume / 20.0)
            print(f"  Effect:        {effect} | {effect_volume:.0f} dB (gain={gain_linear:.3f})")
            print(f"  FX RMS:        {fx_rms_val:.4f} | peak={fx_peak_val:.4f}")

            # Espectro do FX (bandas)
            fx_mono = fx_audio[0] if fx_audio.ndim == 2 else fx_audio
            fft = np.abs(np.fft.rfft(fx_mono))
            freqs = np.fft.rfftfreq(len(fx_mono), 1/sr)
            sub = np.mean(fft[(freqs >= 20) & (freqs < 100)]**2)
            low = np.mean(fft[(freqs >= 100) & (freqs < 300)]**2)
            mid = np.mean(fft[(freqs >= 300) & (freqs < 3000)]**2)
            hi = np.mean(fft[(freqs >= 3000) & (freqs < 10000)]**2)
            total = sub + low + mid + hi
            if total > 0:
                print(f"  Spectrum:      sub={sub/total*100:.0f}% low={low/total*100:.0f}% mid={mid/total*100:.0f}% hi={hi/total*100:.0f}%")
        except Exception as e:
            print(f"  FX diag:       erro ({e})")

    print("=" * 70 + "\n")


# ─────────────────────────────────────────
# FULL MIX
# ─────────────────────────────────────────

def render_mix(track_infos, playlist, transition_sec=8,
               default_transition="eq_mix", bpm_mode="gradual",
               progress_cb=None):
    """
    Renderiza mix completo.

    track_infos: list of analyze_track() results
    playlist: list of dicts with {cue_in, cue_out, transition, effect, effect_volume}
    progress_cb: optional callback(pct, message)

    Returns (audio_array, sr)
    """
    n_tracks = len(track_infos)
    if n_tracks == 0:
        return None, 0

    def progress(pct, msg=""):
        if progress_cb:
            progress_cb(pct, msg)

    # Target SR
    target_sr = max(info["sr"] for info in track_infos)
    need_stereo = any(info["y"].ndim == 2 for info in track_infos)

    progress(5, "Preparando tracks...")

    # Prepare tracks
    prepared = []
    for i, (info, entry) in enumerate(zip(track_infos, playlist)):
        y = info["y"].copy()
        sr = info["sr"]

        if sr != target_sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            info["beats"] = get_beats(y, target_sr)

        if need_stereo:
            y = ensure_stereo(y)

        # Normalizar loudness por track antes de mixar
        y = normalize_lufs(y, target_sr)

        prepared.append({"y": y, "sr": target_sr})
        progress(5 + int(15 * (i + 1) / n_tracks), f"Track {i+1} preparada ({measure_lufs(y, target_sr):.1f} LUFS)")

    sr = target_sr

    # Build mix
    segments = []
    # Rastrear onde a transição anterior terminou na track atual
    # pra começar o corpo no ponto correto (após phase alignment)
    aligned_corpo_starts = {}  # {track_index: sample_position}

    for i in range(n_tracks):
        entry = playlist[i]
        y = prepared[i]["y"]
        bpm = track_infos[i]["bpm"]
        cue_in = entry.get("cue_in", track_infos[i]["auto_cue_in"])
        cue_out = entry.get("cue_out", track_infos[i]["auto_cue_out"])

        cue_in_samp = int(cue_in * sr)
        cue_out_samp = int(cue_out * sr)

        # Corpo — usar posição alinhada se disponível
        if i == 0:
            corpo = audio_slice(y, cue_in_samp, cue_out_samp)
        elif i in aligned_corpo_starts:
            # Começar de onde a transição anterior REALMENTE terminou
            corpo_start = aligned_corpo_starts[i]
            if corpo_start < cue_out_samp:
                corpo = audio_slice(y, corpo_start, cue_out_samp)
            else:
                corpo = audio_slice(y, cue_in_samp, cue_out_samp)
        else:
            trans_dur_samp = int(transition_sec * sr)
            corpo_start = cue_in_samp + trans_dur_samp
            if corpo_start < cue_out_samp:
                corpo = audio_slice(y, corpo_start, cue_out_samp)
            else:
                corpo = audio_slice(y, cue_in_samp, cue_out_samp)

        if n_samples(corpo) > 0:
            segments.append(corpo)

        base_pct = 20 + int(60 * i / n_tracks)
        progress(base_pct, f"Processando track {i+1}/{n_tracks}")

        # Transição
        if i < n_tracks - 1:
            next_entry = playlist[i + 1]
            y_next = prepared[i + 1]["y"]
            bpm_next = track_infos[i + 1]["bpm"]

            trans_type = entry.get("transition", default_transition)
            trans_func = get_transition(trans_type)
            # Duração por transição (se definida) ou global
            this_trans_sec = entry.get("transition_sec") or transition_sec
            trans_dur_samp = int(this_trans_sec * sr)

            t1_start = cue_out_samp
            seg_out = audio_slice(y, t1_start, min(t1_start + trans_dur_samp, n_samples(y)))
            if n_samples(seg_out) < trans_dur_samp:
                seg_out = audio_pad(seg_out, trans_dur_samp - n_samples(seg_out))

            next_cue_in = next_entry.get("cue_in", track_infos[i + 1]["auto_cue_in"])
            t2_start_samp = int(next_cue_in * sr)
            seg_in = audio_slice(y_next, t2_start_samp,
                                 min(t2_start_samp + trans_dur_samp, n_samples(y_next)))
            if n_samples(seg_in) < trans_dur_samp:
                seg_in = audio_pad(seg_in, trans_dur_samp - n_samples(seg_in))

            # BPM
            if bpm_mode == "gradual" and abs(bpm - bpm_next) > 0.5:
                seg_out = time_stretch_audio(seg_out, sr, bpm, bpm_next)
                min_n = min(n_samples(seg_out), n_samples(seg_in))
                seg_out = audio_slice(seg_out, 0, min_n)
                seg_in = audio_slice(seg_in, 0, min_n)

            align_bpm = bpm_next if bpm_mode == "gradual" else track_infos[0]["bpm"]

            # Phase align (passar bpm1 original quando houve stretch)
            src_bpm1 = bpm if (bpm_mode == "gradual" and abs(bpm - bpm_next) > 0.5) else None
            start2_aligned = align_and_verify(
                y, sr, y_next, t1_start / sr, next_cue_in,
                align_bpm, this_trans_sec, bpm1=src_bpm1
            )

            t2_aligned = max(0, round(start2_aligned * sr))
            seg_in = audio_slice(y_next, t2_aligned,
                                 min(t2_aligned + trans_dur_samp, n_samples(y_next)))
            if n_samples(seg_in) < trans_dur_samp:
                seg_in = audio_pad(seg_in, trans_dur_samp - n_samples(seg_in))

            min_n = min(n_samples(seg_out), n_samples(seg_in))
            seg_out = audio_slice(seg_out, 0, min_n)
            seg_in = audio_slice(seg_in, 0, min_n)

            mixed = trans_func(seg_out, seg_in, sr=sr, bpm=align_bpm)

            # Registrar onde seg_in REALMENTE terminou pra próxima track
            aligned_corpo_starts[i + 1] = t2_aligned + min_n

            # FX layer na transicao
            entry_effect = entry.get("effect")
            entry_effect_volume = entry.get("effect_volume", -12.0)
            if entry_effect:
                fx_audio = generate_fx(entry_effect, n_samples(mixed), sr)
                if fx_audio is not None:
                    mixed = mix_fx_layer(mixed, fx_audio, entry_effect_volume)

            segments.append(mixed)

            progress(base_pct + 5, f"Transição {i+1}→{i+2} OK")

    # Tail com fade
    last_y = prepared[-1]["y"]
    last_cue_out = playlist[-1].get("cue_out", track_infos[-1]["auto_cue_out"])
    last_cue_out_samp = int(last_cue_out * sr)
    if last_cue_out_samp < n_samples(last_y):
        tail = audio_slice(last_y, last_cue_out_samp, n_samples(last_y))
        fade_samp = min(int(4.0 * sr), n_samples(tail))
        if fade_samp > 0:
            fade = np.linspace(1.0, 0.0, fade_samp)
            if tail.ndim == 2:
                fade = fade[np.newaxis, :]
            tail[..., -fade_samp:] *= fade
        segments.append(tail)

    progress(90, "Concatenando...")

    # Micro-crossfade entre todos os segmentos adjacentes
    # pra eliminar descontinuidades nas junções (corpo→mixed, mixed→corpo)
    for j in range(len(segments) - 1):
        segments[j], segments[j + 1] = crossfade_junction(
            segments[j], segments[j + 1], xfade_ms=30, sr=sr
        )

    output = audio_concat(segments)

    # Normalizar loudness do output final
    output = normalize_lufs(output, sr)

    progress(100, "Pronto!")
    return output, sr


def export_audio(audio, sr, filepath):
    """Exporta audio array pra arquivo WAV."""
    if audio.ndim == 2:
        sf.write(filepath, audio.T, sr)
    else:
        sf.write(filepath, audio, sr)
    return filepath
