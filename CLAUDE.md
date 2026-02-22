# CLAUDE.md - Contexto para o agente Claude Code

## Sobre o projeto
DJMIX é um desktop app para criação automatizada de DJ mixes. O usuário arrasta músicas, configura transições, gera previews individuais e renderiza o mix final. Inspirado no MixMeister Fusion, mas open source, leve e extensível.

## Estrutura do projeto
```
djmix-app/
├── CLAUDE.md                # este arquivo
├── README.md                # documentação pública
├── backend/
│   ├── engine.py            # engine de áudio (~900 linhas)
│   ├── server.py            # FastAPI REST + WebSocket (~570 linhas)
│   ├── fx_layer.py          # gera e mixa efeitos de transição (~90 linhas)
│   ├── effects/             # plugin system de efeitos de transição
│   │   ├── __init__.py      # auto-discovery + registro
│   │   ├── _utils.py        # helpers de síntese (envelopes, filtros)
│   │   ├── noise_riser.py   # sweep de ruído ascendente (build-up)
│   │   ├── sub_boom.py      # impacto grave no final
│   │   ├── downsweep.py     # sweep tonal descendente
│   │   ├── tension_pad.py   # pad tonal sustentado com LFO
│   │   ├── vinyl_crackle.py # textura analógica (estalidos)
│   │   └── reverse_crash.py # crash reverso (build-up metálico)
│   └── transitions/         # plugin system de transições (10 tipos)
│       ├── __init__.py      # auto-discovery + registro
│       ├── _utils.py        # helpers compartilhados (split_bands, make_fade, etc.)
│       ├── crossfade.py     # equal-power crossfade
│       ├── eq_mix.py        # 3-band EQ mix estilo DJM-900
│       ├── filter_sweep.py  # low-pass sweep out + high-pass sweep in
│       ├── echo_out.py      # echo/delay no T1 + fade pra T2
│       ├── cut.py           # corte direto com micro-fade
│       ├── sidechain_pump.py# sidechain ducking estilo EDM
│       ├── tape_stop.py     # efeito tape stop no T1
│       ├── stutter_gate.py  # gate rítmico/stutter
│       ├── reverb_wash.py   # reverb wash na transição
│       └── backspin.py      # efeito backspin/rewind
└── frontend/
    ├── index.html
    ├── package.json         # React 18, wavesurfer.js 7.8, Vite 5.4
    ├── vite.config.js       # proxy /api → localhost:8000, /ws → ws
    └── src/
        ├── main.jsx
        ├── App.jsx          # estado principal, drag-drop, render mix (~574 linhas)
        ├── App.css          # dark DAW theme (~752 linhas)
        ├── api.js           # helpers REST (upload, delete, preview, mix, download)
        ├── components/
        │   ├── TrackCard.jsx       # card de track com header + WaveformView
        │   ├── WaveformView.jsx    # wavesurfer + canvas overlay (cue markers verde/vermelho)
        │   ├── TransitionCard.jsx  # card de transição entre tracks
        │   ├── PreviewWaveform.jsx # mini waveform do preview com zonas marcadas
        │   └── SettingsModal.jsx   # modal de configurações globais
        └── hooks/
            └── useProgress.js      # WebSocket hook para progress tracking
```

## Arquitetura backend

### engine.py - Funções públicas
- `analyze_track(filepath)` → dict com bpm, beats, duration, energy, cue_in, cue_out, drops, breakdowns, key, camelot
- `render_preview(track1, track2, cue_out, cue_in, transition, transition_sec, bpm_mode, effect, effect_volume)` → (audio_array, sr)
- `render_mix(track_infos, playlist, transition_sec, default_transition, bpm_mode, progress_cb)` → (audio_array, sr)
- `export_audio(audio, sr, path)` → salva WAV

### engine.py - Internals importantes
- Áudio SEMPRE em formato stereo `(2, samples)` como numpy float64
- `to_mono()` apenas para análise (BPM, beats), nunca altera áudio original
- `audio_slice(audio, start, end)`, `audio_pad(audio, length)`, `audio_concat(arrays)` — helpers que operam no eixo correto
- `time_stretch_audio(audio, sr, bpm_from, bpm_to)` — stretch canal por canal via librosa
- `normalize_lufs(audio, sr, target_lufs=-14.0)` — normalização loudness via pyloudnorm + peak limit 0.95
- `crossfade_junction(seg_a, seg_b, xfade_ms=30, sr)` — micro-crossfade nas junções pra eliminar descontinuidade IIR

### engine.py - Phase alignment (entre tracks)
- `phase_align(beats1, beats2, start1, start2, bpm)` — alinhamento grosso via beat grid
- `align_and_verify(y1, sr, y2, cue_out, cue_in, bpm, trans_sec)` — iterativo (max 5 iterações):
  - Extrai beats em janela de 2s, cria grids lineares (fit_beat_grid)
  - Mede erro assinado entre beats pareados
  - Aplica micro-correção direta
  - Tolerância 20ms, converge em 1-2 iterações, erro típico <18ms

### engine.py - Diagnóstico de preview
- `_log_preview_diagnostics()` — log detalhado com seções:
  - **Phase Alignment**: shift aplicado, posição original vs alinhada
  - **Segment Lengths**: duração de cada segmento do preview
  - **Energy Analysis**: RMS/peak por segmento, energia por quartil, energy dip ratio
  - **Junction Quality**: diferença de nível nas junções
  - **Beat Alignment**: erro médio de beat matching entre tracks
  - **FX Quality**: nome do efeito, RMS/peak, spectrum (se efeito ativo)

### engine.py - Transições
- Delegadas ao plugin system em `transitions/`
- `get_transition(name)` retorna função `apply_*(seg1, seg2, sr, bpm)` → audio mixado
- 10 transições: crossfade, eq_mix, filter_sweep, echo_out, cut, sidechain_pump, tape_stop, stutter_gate, reverb_wash, backspin

### fx_layer.py - Sistema de efeitos de transição
- `generate_fx(effect_name, duration_samples, sr)`:
  - Usa plugin system (`effects/`) pra gerar áudio sintético
  - Retorna numpy (2, samples) stereo ou None
  - Sem necessidade de beat sync, BPM stretch ou phase alignment
- `mix_fx_layer(mixed_audio, fx_audio, volume_db=-12)`:
  - Soma aditiva com ganho em dB
  - **Soft clip tanh** (threshold=0.85, ceiling=0.95) — comprime apenas picos, preserva volume da música

### effects/ - Efeitos de transição sintéticos
- Auto-discovery em `__init__.py`: scaneia módulos, valida contrato (NAME, LABEL, DESCRIPTION, generate)
- Cada efeito expõe `generate(duration_samples, sr, **kwargs)` → numpy (2, samples) stereo
- 6 efeitos disponíveis:
  - **noise_riser**: ruído branco com LP sweep 200→8000Hz, envelope exponencial crescente
  - **sub_boom**: 80% silêncio + boom grave (sine 45Hz + decay) + sub-rumble crescente
  - **downsweep**: sine sweep exponencial 2000→80Hz com harmônico
  - **tension_pad**: acorde suspensivo (5as) com detune stereo + LFO tremolo + envelope triangle
  - **vinyl_crackle**: ruído rosa + pops aleatórios + LP filter, textura sutil
  - **reverse_crash**: ruído bandpass 2-12kHz com envelope exponencial crescente
- `_utils.py`: helpers compartilhados — `make_envelope()` (6 shapes), `bandpass/lowpass/highpass()`, `ensure_stereo()`, `normalize_peak()`

### server.py - API
- `POST /api/upload` — upload + análise (retorna track metadata + energy profile downsampled 1pt/50ms)
- `DELETE /api/tracks/{id}` — remove track
- `GET /api/tracks/{id}/waveform` — stream do arquivo de áudio
- `GET /api/transitions` — lista transições disponíveis
- `GET /api/effects` — lista efeitos disponíveis com label e description
- `POST /api/preview` — renderiza preview de transição (context_sec=4, retorna WAV blob)
- `POST /api/mix` — renderiza mix completo
- `GET /api/mix/download` — download do mix renderizado
- `WebSocket /ws/progress` — progresso em tempo real {pct, message}

## Decisões técnicas consolidadas

### Áudio
- Sample rate: 44100Hz (preservado do input, sem resample)
- Canais: sempre stereo (2, samples). Nunca converter pra mono exceto pra análise
- BPM detection: 3 métodos independentes (librosa.beat, onset_strength + autocorrelation, tempogram), voto por mediana
- Beat grid: regressão linear sobre beat_times pra grid uniforme (`fit_beat_grid`)
- Phase alignment entre tracks: iterativo com micro-correção assinada, tolerância 20ms, erro típico <18ms
- Cue points: automáticos via perfil de energia RMS — detecta drops (subida >50%) e breakdowns (queda sustentada >4s abaixo de 35%)
- EQ crossover: 250Hz / 2.5kHz (padrão Pioneer DJM-900)
- Time stretch tracks: librosa.effects.time_stretch, canal por canal
- Loudness normalization: LUFS target -14.0 via pyloudnorm

### BPM modes
- **gradual**: cada track toca no seu BPM original, stretch apenas na zona de transição
- **fixed**: todas as tracks no BPM da primeira

### Efeitos de transição (FX)
- Efeitos sintéticos gerados on-the-fly pra duração exata da transição
- Sem necessidade de beat sync, BPM stretch ou phase alignment (diferente dos antigos beat loops)
- Mixing: soma aditiva + soft clip tanh (preserva volume da música)
- Volume controlável por transição via dropdown + global via settings

### Preview
- Formato: 4s contexto ANTES + N segundos transição + 4s contexto DEPOIS
- Total típico: 16s (com transição de 8s)
- Zona de transição: de 4s até 12s no preview
- Micro-crossfade 30ms nas junções (seg_pre→mixed, mixed→seg_post)

### Frontend
- Layout: vertical full-width, sem sidebar
- Track cards empilhados com transition cards entre eles
- Drag-drop: arrastar arquivos mostra indicador laranja de inserção entre tracks
- Reorder: drag de track card pra nova posição, previews marcam como stale
- Cue points: input numérico + botão de cursor + botão de reset auto
- Preview: manual com botão "Gerar Preview", marca "(desatualizado)" quando cue/tipo muda
- Settings modal: afeta apenas tracks futuras, não retroativo
- WaveformView: shadow DOM do WaveSurfer v7, usa `ws.getWrapper().parentElement` pra scroll, `scrollElRef` pra cleanup

### Design system
- Background: #08080d | Surface: #111118, #191922 | Accent: #f97316 (orange)
- Cue IN: #4ade80 (green) | Cue OUT: #f87171 (red)
- Cards com border-radius 12px, botões 8px
- Waveform: wavesurfer.js, 88px height, 2px bars
- Canvas overlay: energy profile (orange 5% opacity) + cue markers (vertical lines com label tabs)

## Dependências Python
- numpy, scipy (filtros Butterworth, sosfilt)
- librosa (análise BPM, beats, onset, time stretch, key detection)
- soundfile (leitura/escrita WAV)
- pyloudnorm (normalização LUFS)
- fastapi, uvicorn (servidor)
- python-multipart (upload de arquivos)

## Dependências Frontend
- react 18, react-dom 18
- wavesurfer.js 7.8
- vite 5.4

## Convenções de código
- Python: numpy arrays pra áudio, scipy pra filtros, librosa pra análise
- Frontend: componentes funcionais React com hooks, CSS puro (sem Tailwind/frameworks), dark theme
- API: REST pra operações CRUD, WebSocket pra streaming de progresso
- Idioma: português nos comentários, labels do frontend e nomes de variáveis em inglês
- Sem TypeScript (projeto leve, JS puro com JSX)

## Como rodar
```bash
# Backend
cd backend
pip install fastapi uvicorn python-multipart numpy scipy librosa soundfile pyloudnorm
uvicorn server:app --port 8000

# Frontend
cd frontend
npm install
npm run dev  # → http://localhost:3000 (proxy pra backend 8000)
```

## Bugs conhecidos / limitações
- Beat alignment entre tracks pode falhar em trechos de breakdown (poucos transientes pra detecção)
