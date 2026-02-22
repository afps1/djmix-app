import PreviewWaveform from './PreviewWaveform.jsx';

/**
 * Verifica compatibilidade harmônica entre dois códigos Camelot.
 * Retorna: { level: 'perfect'|'compatible'|'energy'|'clash', label, icon }
 *
 * Regras da roda de Camelot:
 * - Mesmo código: perfect (ex: 8A → 8A)
 * - ±1 no número (mesma letra): compatible (ex: 8A → 7A, 8A → 9A)
 * - Mesma posição, troca de letra (relativo maior/menor): compatible (ex: 8A → 8B)
 * - ±2 no número: energy boost (funciona mas com mais tensão)
 * - Resto: clash (choque harmônico provável)
 */
function getCamelotCompat(camelot1, camelot2) {
  if (!camelot1 || !camelot2) return null;

  // Parse: "8A" → { num: 8, letter: 'A' }
  const parse = (c) => {
    const match = c.match(/^(\d+)([AB])$/);
    if (!match) return null;
    return { num: parseInt(match[1]), letter: match[2] };
  };

  const c1 = parse(camelot1);
  const c2 = parse(camelot2);
  if (!c1 || !c2) return null;

  // Distância circular (1-12)
  const dist = Math.min(
    Math.abs(c1.num - c2.num),
    12 - Math.abs(c1.num - c2.num)
  );
  const sameLetter = c1.letter === c2.letter;

  // Mesmo código
  if (dist === 0 && sameLetter) {
    return { level: 'perfect', label: 'Mesma tonalidade', icon: '✓' };
  }
  // Adjacente na mesma coluna (±1)
  if (dist === 1 && sameLetter) {
    return { level: 'compatible', label: 'Compatível', icon: '✓' };
  }
  // Relativo maior/menor (mesmo número, troca letra)
  if (dist === 0 && !sameLetter) {
    return { level: 'compatible', label: 'Relativo', icon: '✓' };
  }
  // ±2 na mesma coluna — energy boost
  if (dist === 2 && sameLetter) {
    return { level: 'energy', label: 'Energy boost', icon: '~' };
  }
  // ±1 com troca de coluna — funciona em alguns contextos
  if (dist === 1 && !sameLetter) {
    return { level: 'energy', label: 'Energy boost', icon: '~' };
  }
  // Resto: clash
  return { level: 'clash', label: 'Choque harmônico', icon: '✕' };
}

export default function TransitionCard({
  fromTrack, toTrack, index,
  transitionType, transitionSec,
  availableTransitions,
  availableEffects,
  selectedEffect,
  onEffectChange,
  onTransitionTypeChange,
  onTransitionDurChange,
  onGeneratePreview,
  previewUrl,
  previewStale,
  generating,
}) {
  const compat = getCamelotCompat(fromTrack?.camelot, toTrack?.camelot);

  return (
    <div className="transition-card">
      <div className="transition-header">
        <span className="transition-arrow">↕</span>
        <span className="transition-label">Transição {index + 1} → {index + 2}</span>

        {compat && (
          <span
            className={`camelot-compat camelot-${compat.level}`}
            title={`${fromTrack.camelot} → ${toTrack.camelot}: ${compat.label}`}
          >
            <span className="camelot-icon">{compat.icon}</span>
            {fromTrack.camelot}→{toTrack.camelot}
          </span>
        )}

        <select
          className="transition-select"
          value={transitionType}
          onChange={(e) => onTransitionTypeChange(e.target.value)}
        >
          {(availableTransitions || []).map(t => (
            <option key={t.name} value={t.name}>{t.label}</option>
          ))}
        </select>

        <select
          className="transition-select fx-select"
          value={selectedEffect || ''}
          onChange={(e) => onEffectChange(e.target.value)}
          title="Efeito de Transição"
        >
          <option value="">Sem efeito</option>
          {(availableEffects || []).map(e => (
            <option key={e.name} value={e.name}>{e.label}</option>
          ))}
        </select>

        <select
          className="transition-select dur-select"
          value={transitionSec}
          onChange={(e) => onTransitionDurChange(parseInt(e.target.value))}
          title="Duração da transição"
        >
          {[4, 6, 8, 12, 16, 24, 32].map(s => (
            <option key={s} value={s}>{s}s</option>
          ))}
        </select>

        <div className="transition-actions">
          {generating ? (
            <button className="btn btn-sm btn-secondary" disabled>
              <span className="spinner" style={{ width: 12, height: 12 }} /> Gerando...
            </button>
          ) : (
            <button
              className="btn btn-sm btn-secondary"
              onClick={onGeneratePreview}
            >
              {previewUrl ? '↻ Regerar' : '▶ Gerar Preview'}
            </button>
          )}
        </div>
      </div>

      {/* Generating */}
      {generating && (
        <div className="transition-generating">
          <div className="spinner" />
          Gerando preview da transição...
        </div>
      )}

      {/* Preview with mini waveform */}
      {!generating && previewUrl && (
        <>
          <PreviewWaveform
            blobUrl={previewUrl}
            contextSec={4}
            transitionSec={transitionSec}
          />
          <div className="preview-meta">
            <span>Clique na waveform para play/pause</span>
            {previewStale && <span className="stale-badge">desatualizado</span>}
          </div>
        </>
      )}

      {/* Empty */}
      {!generating && !previewUrl && (
        <div className="transition-empty">
          Clique em "Gerar Preview" para ouvir a transição
        </div>
      )}
    </div>
  );
}
