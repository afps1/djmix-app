import { useState } from 'react';

export default function SettingsModal({ settings, onSave, onClose, availableTransitions, availableEffects }) {
  const [local, setLocal] = useState({ ...settings });

  const update = (key, val) => setLocal(prev => ({ ...prev, [key]: val }));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>
          ⚙ Configurações do Mix
          <button className="close-btn" onClick={onClose}>×</button>
        </h2>

        <div className="modal-field">
          <label>Transição padrão (para novas tracks)</label>
          <select value={local.defaultTransition} onChange={(e) => update('defaultTransition', e.target.value)}>
            {(availableTransitions || []).map(t => (
              <option key={t.name} value={t.name}>{t.label}</option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Duração da transição (segundos)</label>
          <input
            type="number"
            min="2"
            max="32"
            value={local.transitionSec}
            onChange={(e) => update('transitionSec', parseInt(e.target.value) || 8)}
          />
        </div>

        <div className="modal-field">
          <label>Modo de BPM</label>
          <div className="modal-radio-group">
            <label className="modal-radio">
              <input
                type="radio"
                name="bpmMode"
                value="gradual"
                checked={local.bpmMode === 'gradual'}
                onChange={() => update('bpmMode', 'gradual')}
              />
              Gradual
            </label>
            <div className="modal-radio-desc">
              Cada track no seu BPM original, stretch só na transição
            </div>

            <label className="modal-radio">
              <input
                type="radio"
                name="bpmMode"
                value="fixed"
                checked={local.bpmMode === 'fixed'}
                onChange={() => update('bpmMode', 'fixed')}
              />
              Fixo
            </label>
            <div className="modal-radio-desc">
              Todas as tracks no BPM da primeira
            </div>
          </div>
        </div>

        {/* Efeitos de Transição */}
        <div className="modal-section-title">Efeitos de Transição</div>

        <div className="modal-field">
          <label>Efeito padrão (para novas transições)</label>
          <select value={local.effect || ''} onChange={(e) => update('effect', e.target.value)}>
            <option value="">Nenhum</option>
            {(availableEffects || []).map(e => (
              <option key={e.name} value={e.name}>{e.label}</option>
            ))}
          </select>
        </div>

        <div className="modal-field">
          <label>Volume do efeito: {local.effectVolume} dB</label>
          <input
            type="range"
            min="-24"
            max="0"
            step="1"
            value={local.effectVolume}
            onChange={(e) => update('effectVolume', parseFloat(e.target.value))}
            className="volume-slider"
          />
          <div className="slider-labels">
            <span>-24 dB</span>
            <span>0 dB</span>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={() => { onSave(local); onClose(); }}>Salvar</button>
        </div>
      </div>
    </div>
  );
}
