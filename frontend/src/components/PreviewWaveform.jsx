import { useEffect, useRef, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';

/**
 * Mini waveform for transition preview.
 * Shows context zones (dimmed) and transition zone (highlighted) with markers.
 *
 * Layout: | context (4s) | transition (Ns) | context (4s) |
 */
export default function PreviewWaveform({ blobUrl, contextSec = 4, transitionSec = 8 }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !blobUrl) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#3a3a5a',
      progressColor: '#f97316',
      cursorColor: '#f97316aa',
      cursorWidth: 1,
      height: 52,
      barWidth: 2,
      barGap: 1,
      barRadius: 1,
      normalize: true,
      interact: true,
      fillParent: true,
    });

    ws.load(blobUrl);
    ws.on('ready', () => drawOverlay(ws));
    ws.on('redraw', () => drawOverlay(ws));
    wsRef.current = ws;

    return () => { ws.destroy(); wsRef.current = null; };
  }, [blobUrl]);

  const drawOverlay = useCallback((ws) => {
    const canvas = canvasRef.current;
    if (!canvas || !ws) return;

    const parent = canvas.parentElement;
    const w = parent.offsetWidth;
    const h = parent.offsetHeight || 52;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, w, h);

    const duration = ws.getDuration();
    if (!duration) return;

    const transStart = contextSec;
    const transEnd = contextSec + transitionSec;

    const x1 = (transStart / duration) * w;
    const x2 = (transEnd / duration) * w;

    // Dim context zones
    ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
    ctx.fillRect(0, 0, x1, h);
    ctx.fillRect(x2, 0, w - x2, h);

    // Transition zone highlight border
    ctx.strokeStyle = 'rgba(249, 115, 22, 0.25)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x1, 0, x2 - x1, h);

    // Start marker
    drawVerticalMarker(ctx, x1, h, '#f97316', '▶ START');
    // End marker
    drawVerticalMarker(ctx, x2, h, '#f97316', 'END ■');

    // Time labels
    ctx.font = '9px system-ui';
    ctx.fillStyle = '#55556a';
    ctx.fillText(formatSec(0), 4, h - 4);
    ctx.fillText(formatSec(transStart), x1 + 4, h - 4);
    ctx.fillText(formatSec(transEnd), x2 + 4, h - 4);
    const endLabel = formatSec(duration);
    ctx.fillText(endLabel, w - ctx.measureText(endLabel).width - 4, h - 4);

  }, [contextSec, transitionSec]);

  const handlePlayPause = useCallback(() => {
    if (wsRef.current) wsRef.current.playPause();
  }, []);

  return (
    <div className="preview-waveform-wrap" onClick={handlePlayPause} style={{ cursor: 'pointer' }}>
      <canvas ref={canvasRef} className="preview-overlay-canvas" />
      <div ref={containerRef} style={{ position: 'relative', zIndex: 2 }} />
    </div>
  );
}

// ── Helpers ──

function drawVerticalMarker(ctx, x, h, color, label) {
  // Dashed line
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash([4, 3]);
  ctx.beginPath();
  ctx.moveTo(x, 0);
  ctx.lineTo(x, h);
  ctx.stroke();
  ctx.setLineDash([]);

  // Label tab
  ctx.font = 'bold 8px system-ui';
  const tw = ctx.measureText(label).width + 6;
  const tabX = label.startsWith('END') ? x - tw - 1 : x + 1;
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.85;
  ctx.beginPath();
  ctx.roundRect(tabX, 1, tw, 13, 2);
  ctx.fill();
  ctx.globalAlpha = 1.0;
  ctx.fillStyle = '#000';
  ctx.fillText(label, tabX + 3, 10);
}

function formatSec(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
