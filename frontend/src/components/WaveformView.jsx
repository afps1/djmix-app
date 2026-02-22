import { useEffect, useRef, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { getWaveformUrl } from '../api.js';

export default function WaveformView({ track, cueIn, cueOut, onCueInChange, onCueOutChange }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const readyRef = useRef(false);
  const onScrollRef = useRef(null);
  const scrollElRef = useRef(null);

  // Refs pra evitar stale closures nos event handlers do wavesurfer
  const cueInRef = useRef(cueIn);
  const cueOutRef = useRef(cueOut);
  const trackRef = useRef(track);
  cueInRef.current = cueIn;
  cueOutRef.current = cueOut;
  trackRef.current = track;

  // Função de desenho — sempre lê valores atuais dos refs
  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const ws = wsRef.current;
    const t = trackRef.current;
    if (!canvas || !ws || !t) return;

    const parent = canvas.parentElement;
    const w = parent.offsetWidth;
    const h = parent.offsetHeight || 88;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, w, h);

    const duration = t.duration;
    if (!duration) return;

    // Helper: time → x pixel (accounting for zoom/scroll)
    // Com fillParent:true, o pxPerSec efetivo é max(minPxPerSec, containerWidth/duration)
    const minPxPerSec = ws.options.minPxPerSec || 10;
    const naturalPxPerSec = w / duration;
    const effectivePxPerSec = Math.max(minPxPerSec, naturalPxPerSec);
    const totalWidth = duration * effectivePxPerSec;

    // Buscar scrollLeft via API do wavesurfer — elementos internos estão
    // dentro de shadow DOM, então getElementsByTagName não os encontra
    let scrollLeft = 0;
    const wrapper = ws.getWrapper?.();
    if (wrapper?.parentElement) {
      scrollLeft = wrapper.parentElement.scrollLeft;
    }

    const timeToX = (sec) => {
      if (totalWidth <= w) {
        // Sem scroll, cabe na view
        return (sec / duration) * w;
      }
      // Zoomed: posição baseada em pixels menos scroll
      return (sec / duration) * totalWidth - scrollLeft;
    };

    // Draw energy profile (subtle fill)
    if (t.energy) {
      const data = t.energy;
      const step = w / data.length;
      ctx.fillStyle = 'rgba(249, 115, 22, 0.05)';
      ctx.beginPath();
      ctx.moveTo(0, h);
      for (let i = 0; i < data.length; i++) {
        ctx.lineTo(i * step, h - data[i] * h * 0.85);
      }
      ctx.lineTo(w, h);
      ctx.closePath();
      ctx.fill();
    }

    // Draw cue markers
    const drawMarker = (timeSec, color, label) => {
      if (timeSec == null || timeSec < 0) return;
      const x = timeToX(timeSec);
      if (x < -2 || x > w + 2) return; // off screen

      // Vertical line
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();

      // Label tab at top
      ctx.font = 'bold 9px system-ui';
      const textW = ctx.measureText(label).width + 8;
      const tabH = 16;
      const tabX = Math.min(x, w - textW - 2);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(tabX, 1, textW, tabH, 3);
      ctx.fill();
      ctx.fillStyle = '#000';
      ctx.fillText(label, tabX + 4, 12);

      // Glow effect
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.2;
      ctx.beginPath();
      ctx.moveTo(x - 1, 0);
      ctx.lineTo(x - 1, h);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x + 1, 0);
      ctx.lineTo(x + 1, h);
      ctx.stroke();
      ctx.globalAlpha = 1.0;
    };

    drawMarker(cueInRef.current, '#4ade80', 'IN');
    drawMarker(cueOutRef.current, '#f87171', 'OUT');

  }, []); // Sem dependências — lê tudo dos refs

  // Create wavesurfer
  useEffect(() => {
    if (!containerRef.current || !track) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#4a4a6a',
      progressColor: '#f97316',
      cursorColor: '#f9731688',
      cursorWidth: 1,
      height: 88,
      barWidth: 2,
      barGap: 1,
      barRadius: 1,
      normalize: true,
      interact: true,
      fillParent: true,
      minPxPerSec: 10,
      autoScroll: true,
    });

    wsRef.current = ws;
    const container = containerRef.current; // salvar referência pro cleanup

    ws.load(getWaveformUrl(track.id));

    ws.on('ready', () => {
      readyRef.current = true;

      // Scroll listener direto no scroll container do wavesurfer —
      // elementos internos estão em shadow DOM, então capture no containerRef não funciona
      const scrollEl = ws.getWrapper()?.parentElement;
      if (scrollEl) {
        scrollElRef.current = scrollEl;
        onScrollRef.current = () => drawOverlay();
        scrollEl.addEventListener('scroll', onScrollRef.current);
      }

      drawOverlay();
    });

    ws.on('redraw', () => drawOverlay());

    // wavesurfer v7 emite 'scroll' quando a view rola — backup pro capture listener
    ws.on('scroll', () => requestAnimationFrame(() => drawOverlay()));

    return () => {
      if (scrollElRef.current && onScrollRef.current) {
        scrollElRef.current.removeEventListener('scroll', onScrollRef.current);
      }
      scrollElRef.current = null;
      onScrollRef.current = null;
      ws.destroy();
      wsRef.current = null;
      readyRef.current = false;
    };
  }, [track?.id, drawOverlay]);

  // Redraw overlay when cue points change
  useEffect(() => {
    drawOverlay();
  }, [cueIn, cueOut, track?.energy, drawOverlay]);

  const handlePlayPause = useCallback(() => {
    if (wsRef.current) wsRef.current.playPause();
  }, []);

  const handleZoom = useCallback((dir) => {
    if (!wsRef.current) return;
    const cur = wsRef.current.options.minPxPerSec || 10;
    const next = dir > 0 ? Math.min(cur * 1.5, 500) : Math.max(cur / 1.5, 5);
    wsRef.current.zoom(next);
    // Redraw after zoom
    setTimeout(() => drawOverlay(), 50);
  }, [drawOverlay]);

  const setCueFromCursor = useCallback((which) => {
    if (!wsRef.current) return;
    const t = wsRef.current.getCurrentTime();
    if (which === 'in') onCueInChange?.(parseFloat(t.toFixed(2)));
    else onCueOutChange?.(parseFloat(t.toFixed(2)));
  }, [onCueInChange, onCueOutChange]);

  if (!track) return null;

  return (
    <>
      <div className="waveform-wrap">
        <canvas ref={canvasRef} className="overlay-canvas" />
        <div ref={containerRef} style={{ position: 'relative', zIndex: 2 }} />
        <div className="waveform-controls">
          <button className="waveform-btn" onClick={handlePlayPause} title="Play/Pause">▶</button>
          <button className="waveform-btn" onClick={() => handleZoom(1)} title="Zoom in">+</button>
          <button className="waveform-btn" onClick={() => handleZoom(-1)} title="Zoom out">−</button>
        </div>
      </div>

      <div className="cue-row">
        <div className="cue-group">
          <span className="cue-label cue-label-in">▶ IN</span>
          <input
            className="cue-input"
            type="number"
            step="0.1"
            value={cueIn ?? ''}
            onChange={(e) => onCueInChange?.(parseFloat(e.target.value) || 0)}
          />
          <span className="cue-method">{track.cue_in_method}</span>
          <button className="cue-btn" onClick={() => onCueInChange?.(track.auto_cue_in)} title="Reset auto">↺</button>
          <button className="cue-btn" onClick={() => setCueFromCursor('in')} title="Posição do cursor">📍</button>
        </div>

        <div className="cue-group">
          <span className="cue-label cue-label-out">■ OUT</span>
          <input
            className="cue-input"
            type="number"
            step="0.1"
            value={cueOut ?? ''}
            onChange={(e) => onCueOutChange?.(parseFloat(e.target.value) || 0)}
          />
          <span className="cue-method">{track.cue_out_method}</span>
          <button className="cue-btn" onClick={() => onCueOutChange?.(track.auto_cue_out)} title="Reset auto">↺</button>
          <button className="cue-btn" onClick={() => setCueFromCursor('out')} title="Posição do cursor">📍</button>
        </div>

        <div className="track-analysis">
          {track.drops?.length || 0} drops · {track.breakdowns?.length || 0} breakdowns
        </div>
      </div>
    </>
  );
}
