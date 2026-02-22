"""
DJMIX Server — FastAPI backend

Endpoints:
  POST /api/upload          Upload a track
  GET  /api/tracks          List uploaded tracks
  GET  /api/tracks/{id}     Get track analysis data
  DEL  /api/tracks/{id}     Remove a track
  GET  /api/tracks/{id}/waveform   Get waveform audio for wavesurfer
  POST /api/preview         Render transition preview
  POST /api/mix             Render full mix (format: wav|mp3)
  GET  /api/mix/download    Download rendered mix
  GET  /api/transitions     List available transition types
  POST /api/project/save    Save project state
  POST /api/project/load    Load project state
  WS   /ws/progress         Real-time progress updates
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio, json, os, uuid, shutil, tempfile, traceback, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import soundfile as sf
import numpy as np

import engine
from transitions import TRANSITION_INFO
from effects import EFFECT_INFO

# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────

app = FastAPI(title="DJMIX API", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for heavy CPU work (librosa)
executor = ThreadPoolExecutor(max_workers=2)

# Storage
DATA_DIR = Path(tempfile.mkdtemp(prefix="djmix_"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory track store
# key: track_id → {id, filename, filepath, analysis: {...}}
tracks = {}

# Current mix output
current_mix_path = None
current_mix_format = "wav"

# WebSocket connections for progress
ws_connections: list[WebSocket] = []


# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────

class PreviewRequest(BaseModel):
    track1_id: str
    track2_id: str
    cue_out: float         # seconds — where T1 transitions out
    cue_in: float          # seconds — where T2 enters
    transition: str = "eq_mix"
    transition_sec: float = 8.0
    bpm_mode: str = "gradual"
    effect: Optional[str] = None          # nome do efeito ou None
    effect_volume: float = -12.0          # volume do efeito em dB

class PlaylistEntry(BaseModel):
    track_id: str
    cue_in: Optional[float] = None      # seconds (None = auto)
    cue_out: Optional[float] = None     # seconds (None = auto)
    transition: Optional[str] = None    # None = default
    transition_sec: Optional[float] = None  # duração por transição (None = global)
    effect: Optional[str] = None        # efeito de transição
    effect_volume: float = -12.0        # volume do efeito em dB

class MixRequest(BaseModel):
    playlist: list[PlaylistEntry]
    transition_sec: float = 8.0
    default_transition: str = "eq_mix"
    bpm_mode: str = "gradual"
    format: str = "wav"  # "wav" ou "mp3"


# ─────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────

@app.websocket("/ws/progress")
async def ws_progress(ws: WebSocket):
    await ws.accept()
    ws_connections.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_connections.remove(ws)


async def broadcast_progress(pct: int, message: str):
    data = json.dumps({"pct": pct, "message": message})
    dead = []
    for ws in ws_connections:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_connections.remove(ws)


# ─────────────────────────────────────────
# TRACK ENDPOINTS
# ─────────────────────────────────────────

@app.post("/api/upload")
async def upload_track(file: UploadFile = File(...)):
    """Upload and analyze a track."""
    # Validate
    ext = Path(file.filename).suffix.lower()
    if ext not in (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"):
        raise HTTPException(400, f"Formato não suportado: {ext}")

    track_id = str(uuid.uuid4())[:8]
    filepath = UPLOAD_DIR / f"{track_id}{ext}"

    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Analyze in thread pool (heavy CPU)
    await broadcast_progress(0, f"Analisando {file.filename}...")

    loop = asyncio.get_event_loop()
    try:
        analysis = await loop.run_in_executor(
            executor, engine.analyze_track, str(filepath)
        )
    except Exception as e:
        filepath.unlink(missing_ok=True)
        raise HTTPException(500, f"Erro na análise: {str(e)}")

    await broadcast_progress(100, f"{file.filename} analisado!")

    # Store (keep y and sr in memory for processing, don't serialize)
    tracks[track_id] = {
        "id": track_id,
        "filename": file.filename,
        "filepath": str(filepath),
        "analysis": analysis,  # includes y, sr (numpy arrays)
    }

    # Return metadata (without audio arrays)
    return _track_metadata(track_id)


@app.get("/api/tracks")
async def list_tracks():
    """List all uploaded tracks with metadata."""
    return [_track_metadata(tid) for tid in tracks]


@app.get("/api/tracks/{track_id}")
async def get_track(track_id: str):
    """Get detailed analysis for a track."""
    if track_id not in tracks:
        raise HTTPException(404, "Track não encontrada")
    return _track_metadata(track_id)


@app.delete("/api/tracks/{track_id}")
async def delete_track(track_id: str):
    """Remove a track."""
    if track_id not in tracks:
        raise HTTPException(404, "Track não encontrada")
    filepath = Path(tracks[track_id]["filepath"])
    filepath.unlink(missing_ok=True)
    del tracks[track_id]
    return {"status": "ok", "deleted": track_id}


@app.get("/api/tracks/{track_id}/waveform")
async def get_waveform(track_id: str):
    """
    Return the original audio file for wavesurfer.js to render.
    """
    if track_id not in tracks:
        raise HTTPException(404, "Track não encontrada")
    filepath = tracks[track_id]["filepath"]
    return FileResponse(filepath, media_type="audio/mpeg")


def _track_metadata(track_id: str) -> dict:
    """Extract JSON-safe metadata from track info."""
    t = tracks[track_id]
    a = t["analysis"]
    return {
        "id": t["id"],
        "filename": t["filename"],
        "duration": a["duration"],
        "channels": a["channels"],
        "sr": a["sr"],
        "bpm": a["bpm"],
        "bpm_candidates": a["bpm_candidates"],
        "beats": a["beats"],
        "auto_cue_in": a["auto_cue_in"],
        "auto_cue_out": a["auto_cue_out"],
        "cue_in_method": a["cue_in_method"],
        "cue_out_method": a["cue_out_method"],
        "drops": a["drops"],
        "breakdowns": a["breakdowns"],
        "energy": a["energy"],
        "energy_times": a["energy_times"],
        "lufs": a.get("lufs"),
        "key": a.get("key"),
        "camelot": a.get("camelot"),
    }


# ─────────────────────────────────────────
# PREVIEW ENDPOINT
# ─────────────────────────────────────────

@app.post("/api/preview")
async def preview_transition(req: PreviewRequest):
    """Render a short preview of a transition between two tracks."""
    if req.track1_id not in tracks:
        raise HTTPException(404, f"Track {req.track1_id} não encontrada")
    if req.track2_id not in tracks:
        raise HTTPException(404, f"Track {req.track2_id} não encontrada")

    t1_info = tracks[req.track1_id]["analysis"]
    t2_info = tracks[req.track2_id]["analysis"]

    loop = asyncio.get_event_loop()
    try:
        audio, sr = await loop.run_in_executor(executor, lambda: engine.render_preview(
            t1_info, t2_info,
            cue_out_sec=req.cue_out,
            cue_in_sec=req.cue_in,
            transition_type=req.transition,
            transition_sec=req.transition_sec,
            bpm_mode=req.bpm_mode,
            effect=req.effect,
            effect_volume=req.effect_volume,
        ))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no preview: {str(e)}")

    # Export preview
    preview_path = OUTPUT_DIR / "preview.wav"
    engine.export_audio(audio, sr, str(preview_path))

    return FileResponse(str(preview_path), media_type="audio/wav",
                        filename="preview.wav")


# ─────────────────────────────────────────
# MIX ENDPOINT
# ─────────────────────────────────────────

@app.post("/api/mix")
async def render_full_mix(req: MixRequest):
    """Render the complete mix."""
    global current_mix_path, current_mix_format

    # Validate all tracks exist
    for entry in req.playlist:
        if entry.track_id not in tracks:
            raise HTTPException(404, f"Track {entry.track_id} não encontrada")

    # Build track_infos and playlist dicts for engine
    track_infos = []
    playlist_dicts = []

    for entry in req.playlist:
        t = tracks[entry.track_id]
        track_infos.append(t["analysis"])

        pd = {}
        if entry.cue_in is not None:
            pd["cue_in"] = entry.cue_in
        else:
            pd["cue_in"] = t["analysis"]["auto_cue_in"]

        if entry.cue_out is not None:
            pd["cue_out"] = entry.cue_out
        else:
            pd["cue_out"] = t["analysis"]["auto_cue_out"]

        pd["transition"] = entry.transition or req.default_transition
        pd["transition_sec"] = entry.transition_sec  # None = usar global
        pd["effect"] = entry.effect
        pd["effect_volume"] = entry.effect_volume
        playlist_dicts.append(pd)

    # Progress callback (needs to bridge sync→async)
    loop = asyncio.get_event_loop()

    def sync_progress(pct, msg):
        asyncio.run_coroutine_threadsafe(
            broadcast_progress(pct, msg), loop
        )

    try:
        audio, sr = await loop.run_in_executor(executor, lambda: engine.render_mix(
            track_infos=track_infos,
            playlist=playlist_dicts,
            transition_sec=req.transition_sec,
            default_transition=req.default_transition,
            bpm_mode=req.bpm_mode,
            progress_cb=sync_progress,
        ))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no mix: {str(e)}")

    if audio is None:
        raise HTTPException(500, "Mix retornou vazio")

    # Export WAV
    wav_path = OUTPUT_DIR / "mix_output.wav"
    engine.export_audio(audio, sr, str(wav_path))

    duration = engine.n_samples(audio) / sr
    channels = audio.shape[0] if audio.ndim == 2 else 1

    # Converter pra MP3 se solicitado
    if req.format == "mp3":
        await broadcast_progress(95, "Convertendo para MP3...")
        mp3_path = OUTPUT_DIR / "mix_output.mp3"
        try:
            result = await loop.run_in_executor(executor, lambda: subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "320k",
                 "-q:a", "0", str(mp3_path)],
                capture_output=True, text=True
            ))
            if result.returncode != 0:
                raise Exception(f"ffmpeg error: {result.stderr[:200]}")
            current_mix_path = str(mp3_path)
            current_mix_format = "mp3"
        except FileNotFoundError:
            raise HTTPException(500, "ffmpeg não encontrado. Instale com: brew install ffmpeg")
    else:
        current_mix_path = str(wav_path)
        current_mix_format = "wav"

    size_mb = os.path.getsize(current_mix_path) / 1024 / 1024

    return {
        "status": "ok",
        "duration": round(duration, 1),
        "channels": channels,
        "sr": sr,
        "size_mb": round(size_mb, 1),
        "format": current_mix_format,
        "download_url": "/api/mix/download",
    }


@app.get("/api/mix/download")
async def download_mix():
    """Download the rendered mix."""
    if not current_mix_path or not os.path.isfile(current_mix_path):
        raise HTTPException(404, "Nenhum mix renderizado")
    if current_mix_format == "mp3":
        return FileResponse(current_mix_path, media_type="audio/mpeg",
                            filename="djmix_output.mp3")
    return FileResponse(current_mix_path, media_type="audio/wav",
                        filename="djmix_output.wav")


# ─────────────────────────────────────────
# PROJECT SAVE / LOAD
# ─────────────────────────────────────────

class ProjectSaveRequest(BaseModel):
    """Frontend state to persist in the project file."""
    track_order: list[str]                        # [track_id, ...]
    cue_points: dict                              # {track_id: {cueIn, cueOut}}
    transition_types: dict                        # {pairKey: type}
    transition_durations: dict                    # {pairKey: seconds}
    effect_selections: dict                        # {pairKey: effectName}
    settings: dict                                # global settings


@app.post("/api/project/save")
async def save_project(req: ProjectSaveRequest):
    """
    Save project state to a JSON structure.
    Includes file paths + analysis metadata so tracks can be re-loaded.
    """
    # Montar dados das tracks com file paths originais
    track_data = []
    for tid in req.track_order:
        if tid not in tracks:
            continue
        t = tracks[tid]
        a = t["analysis"]
        track_data.append({
            "id": tid,
            "filename": t["filename"],
            "filepath": t["filepath"],
            "bpm": a["bpm"],
            "duration": a["duration"],
            "auto_cue_in": a["auto_cue_in"],
            "auto_cue_out": a["auto_cue_out"],
            "lufs": a.get("lufs"),
            "key": a.get("key"),
            "camelot": a.get("camelot"),
        })

    project = {
        "version": "1.0",
        "tracks": track_data,
        "cue_points": req.cue_points,
        "transition_types": req.transition_types,
        "transition_durations": req.transition_durations,
        "effect_selections": req.effect_selections,
        "settings": req.settings,
    }

    return JSONResponse(content=project)


class ProjectLoadRequest(BaseModel):
    project: dict  # O JSON do projeto salvo


@app.post("/api/project/load")
async def load_project(req: ProjectLoadRequest):
    """
    Load a project: re-analisa tracks que ainda existem no disco.
    Retorna lista de tracks carregadas + estado frontend.
    """
    project = req.project
    loaded_tracks = []
    id_mapping = {}  # old_id → new_id (caso mude)
    errors = []

    loop = asyncio.get_event_loop()

    for i, td in enumerate(project.get("tracks", [])):
        filepath = td.get("filepath", "")
        filename = td.get("filename", "unknown")
        old_id = td.get("id", "")

        await broadcast_progress(
            int((i / max(len(project["tracks"]), 1)) * 90),
            f"Carregando {filename}..."
        )

        # Verificar se arquivo ainda existe
        if not os.path.isfile(filepath):
            errors.append(f"{filename}: arquivo não encontrado em {filepath}")
            continue

        # Gerar novo ID e re-analisar
        track_id = str(uuid.uuid4())[:8]
        id_mapping[old_id] = track_id

        try:
            analysis = await loop.run_in_executor(
                executor, engine.analyze_track, filepath
            )
        except Exception as e:
            errors.append(f"{filename}: erro na análise — {str(e)}")
            continue

        tracks[track_id] = {
            "id": track_id,
            "filename": filename,
            "filepath": filepath,
            "analysis": analysis,
        }

        loaded_tracks.append(_track_metadata(track_id))

    await broadcast_progress(100, f"Projeto carregado! {len(loaded_tracks)} tracks")

    # Remapear IDs no estado do frontend
    def remap_dict(d):
        """Remapeia chaves que contém IDs antigos para novos IDs."""
        result = {}
        for key, val in d.items():
            new_key = key
            for old, new in id_mapping.items():
                new_key = new_key.replace(old, new)
            result[new_key] = val
        return result

    return {
        "status": "ok",
        "tracks": loaded_tracks,
        "track_order": [id_mapping[td["id"]] for td in project.get("tracks", [])
                        if td.get("id") in id_mapping],
        "cue_points": remap_dict(project.get("cue_points", {})),
        "transition_types": remap_dict(project.get("transition_types", {})),
        "transition_durations": remap_dict(project.get("transition_durations", {})),
        "effect_selections": remap_dict(project.get("effect_selections", {})),
        "settings": project.get("settings", {}),
        "errors": errors,
    }


# ─────────────────────────────────────────
# INFO ENDPOINTS
# ─────────────────────────────────────────

@app.get("/api/transitions")
async def list_transitions():
    """List available transition types with labels and descriptions."""
    return {
        "transitions": TRANSITION_INFO,
        "default": "eq_mix",
    }


@app.get("/api/effects")
async def list_effects():
    """List available transition effects."""
    return {
        "effects": EFFECT_INFO,
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "tracks_loaded": len(tracks),
        "data_dir": str(DATA_DIR),
    }


# ─────────────────────────────────────────
# STATIC FILES (React build — Phase 2)
# ─────────────────────────────────────────

# In production, serve React build:
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "build"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ─────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────

@app.on_event("shutdown")
async def cleanup():
    shutil.rmtree(DATA_DIR, ignore_errors=True)
