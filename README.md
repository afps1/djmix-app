# DJMIX

Automix de DJ open source. Arraste suas musicas, configure transicoes e renderize mixes profissionais com deteccao automatica de BPM, phase alignment e key detection.

Inspirado no MixMeister Fusion — leve, extensivel e 100% local.

## Features

- Analise automatica: BPM (3 metodos), beat grid, cue points, energia, key/Camelot
- 10 tipos de transicao (EQ Mix, Filter Sweep, Echo Out, Backspin, Tape Stop, ...)
- 12 efeitos de transicao sinteticos (Noise Riser, Siren Rise, Sub Boom, ...)
- Phase alignment iterativo entre tracks (erro tipico <18ms)
- Normalizacao LUFS (-14 dB) por track
- Drag & drop de arquivos + reorder visual
- Preview individual de cada transicao
- Render do mix completo (WAV ou MP3)
- Salvar/carregar projetos (JSON)
- Compatibilidade harmonica (Camelot Wheel)
- Interface dark theme estilo DAW

## Quick Start

```bash
git clone https://github.com/SEU_USUARIO/djmix-app.git
cd djmix-app
make install
make run
```

O app abre automaticamente em `http://localhost:8000`.

## Setup manual (sem Make)

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Linux/Mac
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
npm run build

# Rodar
cd ..
.venv/bin/python launcher.py     # ou: python launcher.py (se venv ativo)
```

## Comandos

| Comando | Descricao |
|---------|-----------|
| `make install` | Instala tudo (Python + Node + build) |
| `make run` | Builda frontend e inicia o app |
| `make dev` | Backend + frontend com hot reload |
| `make build` | Builda apenas o frontend |
| `make clean` | Remove venv, node_modules, build |

## Arquitetura

```
djmix-app/
├── launcher.py          # Entry point (inicia server + abre browser)
├── Makefile             # Automacao de setup e execucao
├── backend/
│   ├── engine.py        # Motor de audio (analise, stretch, mix, phase align)
│   ├── server.py        # FastAPI REST + WebSocket
│   ├── fx_layer.py      # Geracao e mix de efeitos de transicao
│   ├── effects/         # 12 efeitos sinteticos (plugin system)
│   └── transitions/     # 10 tipos de transicao (plugin system)
└── frontend/
    └── src/             # React 18 + wavesurfer.js 7.8
```

## Transicoes

| Nome | Descricao |
|------|-----------|
| EQ Mix | Mix de 3 bandas estilo Pioneer DJM-900 |
| Crossfade | Equal-power crossfade |
| Filter Sweep | LP sweep out + HP sweep in |
| Echo Out | Echo/delay no T1 + fade |
| Cut | Corte direto com micro-fade |
| Sidechain Pump | Ducking estilo EDM |
| Tape Stop | Efeito tape stop no T1 |
| Stutter Gate | Gate ritmico/stutter |
| Reverb Wash | Reverb wash na transicao |
| Backspin | Efeito backspin/rewind |

## Efeitos de Transicao

| Nome | Descricao |
|------|-----------|
| Noise Riser | Sweep de ruido ascendente (build-up) |
| Reverse Crash | Crash reverso (build-up metalico) |
| Siren Rise | Sirene ascendente com vibrato |
| Shimmer Rise | Harmonicos agudos etereos |
| Sub Boom | Impacto grave no final |
| Impact Clap | Clap reverberado no final |
| Downsweep | Sweep tonal descendente |
| Tension Pad | Pad tonal sustentado com LFO |
| White Noise Wash | Textura de ruido constante |
| Vinyl Crackle | Estalidos de vinil analogico |
| Telephone Filter | Banda que abre gradualmente |
| Laser Zap | Sweeps rapidos sci-fi |

## Requisitos

- Python 3.10+
- Node.js 18+
- ffmpeg (opcional, para export MP3)

## Licenca

MIT
