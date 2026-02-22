import { useState, useCallback, useEffect, useRef } from 'react';
import './App.css';
import TrackCard from './components/TrackCard.jsx';
import TransitionCard from './components/TransitionCard.jsx';
import SettingsModal from './components/SettingsModal.jsx';
import { useProgress } from './hooks/useProgress.js';
import * as api from './api.js';

export default function App() {
  const [tracks, setTracks] = useState([]);
  const [cuePoints, setCuePoints] = useState({});
  const [transitionTypes, setTransitionTypes] = useState({});
  const [previews, setPreviews] = useState({});
  const [generating, setGenerating] = useState({});
  const [availableTransitions, setAvailableTransitions] = useState([]);
  const [availableEffects, setAvailableEffects] = useState([]);
  const [effectSelections, setEffectSelections] = useState({});    // {pairKey: effectName}
  const [transitionDurations, setTransitionDurations] = useState({}); // {pairKey: seconds}
  const [settings, setSettings] = useState({ defaultTransition: 'eq_mix', transitionSec: 8, bpmMode: 'gradual', effect: '', effectVolume: -12 });
  const [showSettings, setShowSettings] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [mixResult, setMixResult] = useState(null);
  const [toast, setToast] = useState(null);
  const [dragTrackIdx, setDragTrackIdx] = useState(null);
  const [fileDragOver, setFileDragOver] = useState(null);
  const [fileDragActive, setFileDragActive] = useState(false);

  const { progress, reset: resetProgress } = useProgress();
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.getTransitions().then(d => setAvailableTransitions(d.transitions || [])).catch(() => {});
    api.getEffects().then(d => setAvailableEffects(d.effects || [])).catch(() => {});
  }, []);

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  // ── Transition key helpers ──
  const getTransitionType = useCallback((i, currentTracks) => {
    const t = currentTracks || tracks;
    if (i < 0 || i >= t.length - 1) return settings.defaultTransition;
    const key = `${t[i].id}-${t[i + 1].id}`;
    return transitionTypes[key] || settings.defaultTransition;
  }, [tracks, transitionTypes, settings.defaultTransition]);

  // ── Upload & Insert ──
  const insertTrack = useCallback(async (file, insertAt = -1) => {
    try {
      showToast(`Analisando ${file.name}...`);
      const track = await api.uploadTrack(file);

      setTracks(prev => {
        const next = [...prev];
        const idx = insertAt >= 0 ? insertAt : next.length;
        next.splice(idx, 0, track);
        return next;
      });

      setCuePoints(prev => ({
        ...prev,
        [track.id]: { cueIn: track.auto_cue_in, cueOut: track.auto_cue_out },
      }));

      showToast(`${file.name} carregado!`, 'success');

      setTimeout(() => {
        const el = document.getElementById(`track-${track.id}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 200);

      return track;
    } catch (e) {
      showToast(`Erro: ${e.message}`, 'error');
      return null;
    }
  }, [showToast]);

  // ── Remove ──
  const handleRemove = useCallback(async (trackId) => {
    try {
      await api.deleteTrack(trackId);
      setTracks(prev => prev.filter(t => t.id !== trackId));
      setCuePoints(prev => { const n = { ...prev }; delete n[trackId]; return n; });
      setPreviews(prev => {
        const n = {};
        for (const [k, v] of Object.entries(prev)) {
          if (!k.includes(trackId)) n[k] = v;
          else if (v.url) URL.revokeObjectURL(v.url);
        }
        return n;
      });
    } catch (e) {
      showToast(`Erro: ${e.message}`, 'error');
    }
  }, [showToast]);

  // ── Reorder ──
  const handleReorder = useCallback((fromIdx, toIdx) => {
    if (fromIdx === toIdx) return;
    setTracks(prev => {
      const next = [...prev];
      const [item] = next.splice(fromIdx, 1);
      next.splice(toIdx > fromIdx ? toIdx - 1 : toIdx, 0, item);
      return next;
    });
    setPreviews(prev => {
      const next = {};
      for (const [k, v] of Object.entries(prev)) {
        next[k] = { ...v, stale: true };
      }
      return next;
    });
  }, []);

  // ── Cue changes ──
  const handleCueInChange = useCallback((trackId, val) => {
    setCuePoints(prev => ({ ...prev, [trackId]: { ...prev[trackId], cueIn: val } }));
    setPreviews(prev => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        if (key.includes(trackId)) next[key] = { ...next[key], stale: true };
      }
      return next;
    });
  }, []);

  const handleCueOutChange = useCallback((trackId, val) => {
    setCuePoints(prev => ({ ...prev, [trackId]: { ...prev[trackId], cueOut: val } }));
    setPreviews(prev => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        if (key.includes(trackId)) next[key] = { ...next[key], stale: true };
      }
      return next;
    });
  }, []);

  // ── Transition type change ──
  const handleTransitionTypeChange = useCallback((idx, type) => {
    const key = `${tracks[idx].id}-${tracks[idx + 1].id}`;
    setTransitionTypes(prev => ({ ...prev, [key]: type }));
    setPreviews(prev => {
      const next = { ...prev };
      if (next[key]) next[key] = { ...next[key], stale: true };
      return next;
    });
  }, [tracks]);

  // ── Effect selection change ──
  const handleEffectChange = useCallback((idx, effectName) => {
    const key = `${tracks[idx].id}-${tracks[idx + 1].id}`;
    setEffectSelections(prev => ({ ...prev, [key]: effectName }));
    setPreviews(prev => {
      const next = { ...prev };
      if (next[key]) next[key] = { ...next[key], stale: true };
      return next;
    });
  }, [tracks]);

  // ── Transition duration change (per-transition) ──
  const handleTransitionDurChange = useCallback((idx, sec) => {
    const key = `${tracks[idx].id}-${tracks[idx + 1].id}`;
    setTransitionDurations(prev => ({ ...prev, [key]: sec }));
    setPreviews(prev => {
      const next = { ...prev };
      if (next[key]) next[key] = { ...next[key], stale: true };
      return next;
    });
  }, [tracks]);

  // ── Generate Preview ──
  const handleGeneratePreview = useCallback(async (idx) => {
    if (idx < 0 || idx >= tracks.length - 1) return;
    const t1 = tracks[idx];
    const t2 = tracks[idx + 1];
    const cp1 = cuePoints[t1.id] || {};
    const cp2 = cuePoints[t2.id] || {};
    const key = `${t1.id}-${t2.id}`;
    const transType = getTransitionType(idx);
    const transSec = transitionDurations[key] ?? settings.transitionSec;

    setGenerating(prev => ({ ...prev, [key]: true }));

    // Efeito: usa seleção específica, senão default das settings
    const selectedEffect = effectSelections[key] ?? settings.effect;

    try {
      const blob = await api.renderPreview({
        track1_id: t1.id,
        track2_id: t2.id,
        cue_out: cp1.cueOut ?? t1.auto_cue_out,
        cue_in: cp2.cueIn ?? t2.auto_cue_in,
        transition: transType,
        transition_sec: transSec,
        bpm_mode: settings.bpmMode,
        effect: selectedEffect || null,
        effect_volume: settings.effectVolume,
      });

      if (previews[key]?.url) URL.revokeObjectURL(previews[key].url);
      const url = URL.createObjectURL(blob);
      setPreviews(prev => ({ ...prev, [key]: { url, stale: false } }));
    } catch (e) {
      showToast(`Erro no preview: ${e.message}`, 'error');
    } finally {
      setGenerating(prev => { const n = { ...prev }; delete n[key]; return n; });
    }
  }, [tracks, cuePoints, settings, previews, getTransitionType, effectSelections, showToast]);

  // ── Render Mix ──
  const handleRenderMix = useCallback(async (format = 'wav') => {
    if (tracks.length < 2) return;

    const playlist = tracks.map((t, idx) => {
      const cp = cuePoints[t.id] || {};
      const nextKey = idx < tracks.length - 1 ? `${t.id}-${tracks[idx + 1].id}` : null;
      const effectForTransition = nextKey ? (effectSelections[nextKey] ?? settings.effect) : null;
      return {
        track_id: t.id,
        cue_in: cp.cueIn ?? t.auto_cue_in,
        cue_out: cp.cueOut ?? t.auto_cue_out,
        transition: nextKey ? (transitionTypes[nextKey] || null) : null,
        transition_sec: nextKey ? (transitionDurations[nextKey] ?? null) : null,
        effect: effectForTransition || null,
        effect_volume: settings.effectVolume,
      };
    });

    try {
      setRendering(true);
      setMixResult(null);
      resetProgress();
      showToast(`Renderizando mix (${format.toUpperCase()})...`);

      const result = await api.renderMix({
        playlist,
        transition_sec: settings.transitionSec,
        default_transition: settings.defaultTransition,
        bpm_mode: settings.bpmMode,
        format,
      });

      setMixResult(result);
      showToast(`Mix pronto! ${result.duration}s · ${result.size_mb}MB (${result.format.toUpperCase()})`, 'success');
    } catch (e) {
      showToast(`Erro: ${e.message}`, 'error');
    } finally {
      setRendering(false);
    }
  }, [tracks, cuePoints, transitionTypes, transitionDurations, effectSelections, settings, resetProgress, showToast]);

  const handleDownload = useCallback(() => {
    const ext = mixResult?.format || 'wav';
    const a = document.createElement('a');
    a.href = api.getMixDownloadUrl();
    a.download = `djmix_output.${ext}`;
    a.click();
  }, [mixResult]);

  // ── Save / Load Project ──
  const handleSaveProject = useCallback(async () => {
    try {
      // Salvar transições explicitamente pra cada par (inclui defaults)
      const fullTransTypes = {};
      const fullTransDurs = {};
      const fullEffectSels = {};
      for (let i = 0; i < tracks.length - 1; i++) {
        const key = `${tracks[i].id}-${tracks[i + 1].id}`;
        fullTransTypes[key] = transitionTypes[key] || settings.defaultTransition;
        fullTransDurs[key] = transitionDurations[key] ?? settings.transitionSec;
        fullEffectSels[key] = effectSelections[key] ?? settings.effect ?? '';
      }

      const state = {
        track_order: tracks.map(t => t.id),
        cue_points: cuePoints,
        transition_types: fullTransTypes,
        transition_durations: fullTransDurs,
        effect_selections: fullEffectSels,
        settings,
      };
      const project = await api.saveProject(state);

      // Download como arquivo JSON
      const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'djmix_project.json';
      a.click();
      URL.revokeObjectURL(url);

      showToast('Projeto salvo!', 'success');
    } catch (e) {
      showToast(`Erro ao salvar: ${e.message}`, 'error');
    }
  }, [tracks, cuePoints, transitionTypes, transitionDurations, effectSelections, settings, showToast]);

  const handleLoadProject = useCallback(async (file) => {
    try {
      const text = await file.text();
      const project = JSON.parse(text);
      showToast('Carregando projeto...');
      resetProgress();

      const result = await api.loadProject(project);

      if (result.errors?.length > 0) {
        showToast(`Carregado com avisos: ${result.errors[0]}`, 'error');
      }

      // Restaurar estado
      setTracks(result.tracks || []);

      // Restaurar cue points
      const restoredCues = {};
      for (const [tid, cp] of Object.entries(result.cue_points || {})) {
        restoredCues[tid] = cp;
      }
      setCuePoints(restoredCues);

      setTransitionTypes(result.transition_types || {});
      setTransitionDurations(result.transition_durations || {});
      setEffectSelections(result.effect_selections || {});
      if (result.settings) {
        setSettings(prev => ({ ...prev, ...result.settings }));
      }

      // Limpar previews antigos
      setPreviews({});
      setMixResult(null);

      if (!result.errors?.length) {
        showToast(`Projeto carregado! ${result.tracks?.length || 0} tracks`, 'success');
      }
    } catch (e) {
      showToast(`Erro ao carregar: ${e.message}`, 'error');
    }
  }, [showToast, resetProgress]);

  const projectInputRef = useRef(null);

  // ── File Drag & Drop ──
  const isFileDrag = (e) => e.dataTransfer.types.includes('Files');

  const handleMainDragOver = useCallback((e) => {
    e.preventDefault();
    if (!isFileDrag(e)) return;
    setFileDragActive(true);
  }, []);

  const handleMainDragLeave = useCallback((e) => {
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setFileDragActive(false);
    setFileDragOver(null);
  }, []);

  const handleMainDrop = useCallback(async (e) => {
    e.preventDefault();
    setFileDragActive(false);

    const isFile = isFileDrag(e);
    const trackData = e.dataTransfer.getData('text/plain');

    if (isFile) {
      const files = Array.from(e.dataTransfer.files).filter(f =>
        /\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(f.name)
      );
      const insertAt = fileDragOver ?? tracks.length;
      for (let i = 0; i < files.length; i++) {
        await insertTrack(files[i], insertAt + i);
      }
    } else if (trackData?.startsWith('track:')) {
      const fromIdx = parseInt(trackData.split(':')[1]);
      if (fileDragOver !== null) handleReorder(fromIdx, fileDragOver);
    }

    setFileDragOver(null);
  }, [fileDragOver, tracks.length, insertTrack, handleReorder]);

  const handleGapDragOver = useCallback((e, idx) => {
    e.preventDefault();
    e.stopPropagation();
    setFileDragOver(idx);
  }, []);

  // ── Render ──
  const formatTime = (sec) => `${Math.floor(sec / 60)}:${Math.floor(sec % 60).toString().padStart(2, '0')}`;

  const totalDur = tracks.reduce((sum, t) => {
    const cp = cuePoints[t.id];
    const dur = (cp?.cueOut ?? t.auto_cue_out) - (cp?.cueIn ?? t.auto_cue_in);
    return sum + Math.max(0, dur);
  }, 0);

  return (
    <div className={`app${fileDragActive ? ' file-drag-active' : ''}`}>
      {/* Header */}
      <header className="header">
        <div className="header-logo">🎵 DJ<span>MIX</span></div>
        <div className="header-info">
          {tracks.length} track{tracks.length !== 1 ? 's' : ''}
          {tracks.length > 0 && ` · ~${formatTime(totalDur)}`}
          {tracks.length > 0 && ` · ${settings.bpmMode}`}
        </div>
        <div className="header-actions">
          <button className="btn-icon" onClick={() => setShowSettings(true)} title="Configurações">⚙</button>
          <button className="btn-icon" onClick={handleSaveProject} title="Salvar Projeto" disabled={tracks.length === 0}>💾</button>
          <button className="btn-icon" onClick={() => projectInputRef.current?.click()} title="Carregar Projeto">📂</button>
          <input
            ref={projectInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={(e) => {
              if (e.target.files[0]) handleLoadProject(e.target.files[0]);
              e.target.value = '';
            }}
          />
          <button
            className="btn btn-secondary"
            disabled={tracks.length < 2 || rendering}
            onClick={() => handleRenderMix('wav')}
          >
            {rendering ? 'Renderizando...' : 'Render Mix (WAV)'}
          </button>
          <button
            className="btn btn-primary"
            disabled={tracks.length < 2 || rendering}
            onClick={() => handleRenderMix('mp3')}
          >
            {rendering ? 'Renderizando...' : 'Render Mix (MP3)'}
          </button>
          {mixResult && (
            <button className="btn btn-secondary" onClick={handleDownload}>
              {mixResult.size_mb}MB ({mixResult.format?.toUpperCase()})
            </button>
          )}
        </div>
      </header>

      {/* Main */}
      <div
        ref={scrollRef}
        className="main-scroll"
        onDragOver={handleMainDragOver}
        onDragLeave={handleMainDragLeave}
        onDrop={handleMainDrop}
      >
        {tracks.length === 0 && (
          <div
            className={`empty-drop-zone${fileDragActive ? ' dragover' : ''}`}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="icon">🎵</div>
            <div className="title">Arraste músicas aqui para começar</div>
            <div className="subtitle">MP3, WAV, FLAC, OGG, M4A, AAC</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.flac,.ogg,.m4a,.aac"
              multiple
              style={{ display: 'none' }}
              onChange={async (e) => {
                for (const f of Array.from(e.target.files)) await insertTrack(f);
                e.target.value = '';
              }}
            />
          </div>
        )}

        {tracks.length > 0 && (
          <>
            <div
              className={`drop-zone-gap${fileDragOver === 0 ? ' active' : ''}`}
              onDragOver={(e) => handleGapDragOver(e, 0)}
            >
              {fileDragOver === 0 && <div className="drop-indicator" />}
            </div>

            {tracks.map((track, idx) => (
              <div key={track.id} id={`track-${track.id}`}>
                <TrackCard
                  track={track}
                  index={idx}
                  cueIn={cuePoints[track.id]?.cueIn}
                  cueOut={cuePoints[track.id]?.cueOut}
                  onCueInChange={(v) => handleCueInChange(track.id, v)}
                  onCueOutChange={(v) => handleCueOutChange(track.id, v)}
                  onRemove={handleRemove}
                  onDragStart={(i) => setDragTrackIdx(i)}
                  onDragEnd={() => setDragTrackIdx(null)}
                  dragging={dragTrackIdx === idx}
                />

                {idx < tracks.length - 1 && (
                  <TransitionCard
                    fromTrack={track}
                    toTrack={tracks[idx + 1]}
                    index={idx}
                    transitionType={getTransitionType(idx)}
                    transitionSec={transitionDurations[`${track.id}-${tracks[idx + 1].id}`] ?? settings.transitionSec}
                    availableTransitions={availableTransitions}
                    availableEffects={availableEffects}
                    selectedEffect={effectSelections[`${track.id}-${tracks[idx + 1].id}`] ?? settings.effect}
                    onEffectChange={(effect) => handleEffectChange(idx, effect)}
                    onTransitionTypeChange={(type) => handleTransitionTypeChange(idx, type)}
                    onTransitionDurChange={(sec) => handleTransitionDurChange(idx, sec)}
                    onGeneratePreview={() => handleGeneratePreview(idx)}
                    previewUrl={previews[`${track.id}-${tracks[idx + 1].id}`]?.url}
                    previewStale={previews[`${track.id}-${tracks[idx + 1].id}`]?.stale}
                    generating={!!generating[`${track.id}-${tracks[idx + 1].id}`]}
                  />
                )}

                <div
                  className={`drop-zone-gap${fileDragOver === idx + 1 ? ' active' : ''}`}
                  onDragOver={(e) => handleGapDragOver(e, idx + 1)}
                >
                  {fileDragOver === idx + 1 && <div className="drop-indicator" />}
                </div>
              </div>
            ))}

            {fileDragActive && tracks.length > 0 && (
              <div
                style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)', fontSize: '0.8rem' }}
                onDragOver={(e) => handleGapDragOver(e, tracks.length)}
              >
                Solte para adicionar ao final
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom Bar */}
      <div className="bottom-bar">
        {rendering || progress.pct > 0 ? (
          <div className="progress-section">
            <div className="progress-bar-bg">
              <div className="progress-bar-fill" style={{ width: `${progress.pct}%` }} />
            </div>
            <div className="progress-text">{progress.pct}% — {progress.message}</div>
          </div>
        ) : (
          <div style={{ flex: 1 }} />
        )}

        {mixResult && !rendering && (
          <div className="mix-result">
            ✓ {mixResult.duration}s · {mixResult.channels}ch · {mixResult.sr}Hz
          </div>
        )}
      </div>

      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={setSettings}
          onClose={() => setShowSettings(false)}
          availableTransitions={availableTransitions}
          availableEffects={availableEffects}
        />
      )}

      {toast && <div className={`toast ${toast.type || ''}`}>{toast.message}</div>}
    </div>
  );
}
