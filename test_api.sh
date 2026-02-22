#!/bin/bash
# ─────────────────────────────────────────
# DJMIX API — Test Script
#
# Uso:
#   1. Inicie o servidor:  cd backend && uvicorn server:app --port 8000
#   2. Em outro terminal:  bash test_api.sh
# ─────────────────────────────────────────

BASE="http://localhost:8000"

echo "═══════════════════════════════════════"
echo "  DJMIX API — Testes"
echo "═══════════════════════════════════════"

# Health check
echo -e "\n─── Health ───"
curl -s "$BASE/api/health" | python3 -m json.tool

# Lista transições
echo -e "\n─── Transições disponíveis ───"
curl -s "$BASE/api/transitions" | python3 -m json.tool

# Upload track 1
echo -e "\n─── Upload track 1 ───"
T1=$(curl -s -X POST "$BASE/api/upload" \
    -F "file=@techno.mp3" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Track 1 ID: $T1"

# Upload track 2
echo -e "\n─── Upload track 2 ───"
T2=$(curl -s -X POST "$BASE/api/upload" \
    -F "file=@life.mp3" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Track 2 ID: $T2"

# List tracks
echo -e "\n─── Tracks carregadas ───"
curl -s "$BASE/api/tracks" | python3 -c "
import sys, json
tracks = json.load(sys.stdin)
for t in tracks:
    print(f\"  {t['id']} | {t['filename']} | {t['bpm']:.1f} BPM | {t['duration']:.1f}s\")
    print(f\"    cue_in: {t['auto_cue_in']:.1f}s ({t['cue_in_method']}) | cue_out: {t['auto_cue_out']:.1f}s ({t['cue_out_method']})\")
    print(f\"    drops: {len(t['drops'])} | breakdowns: {len(t['breakdowns'])}\")
"

# Preview
echo -e "\n─── Preview da transição ───"
curl -s -X POST "$BASE/api/preview" \
    -H "Content-Type: application/json" \
    -d "{
        \"track1_id\": \"$T1\",
        \"track2_id\": \"$T2\",
        \"cue_out\": $(curl -s "$BASE/api/tracks/$T1" | python3 -c "import sys,json; print(json.load(sys.stdin)['auto_cue_out'])"),
        \"cue_in\": 30.0,
        \"transition\": \"eq_mix\"
    }" --output preview.wav
echo "→ preview.wav salvo ($(du -h preview.wav | cut -f1))"

# Full mix
echo -e "\n─── Mix completo ───"
CUE_OUT_T1=$(curl -s "$BASE/api/tracks/$T1" | python3 -c "import sys,json; print(json.load(sys.stdin)['auto_cue_out'])")
curl -s -X POST "$BASE/api/mix" \
    -H "Content-Type: application/json" \
    -d "{
        \"playlist\": [
            {\"track_id\": \"$T1\", \"cue_in\": 0, \"cue_out\": $CUE_OUT_T1},
            {\"track_id\": \"$T2\", \"cue_in\": 30.0}
        ],
        \"default_transition\": \"eq_mix\",
        \"bpm_mode\": \"gradual\"
    }" | python3 -m json.tool

# Download mix
echo -e "\n─── Download do mix ───"
curl -s "$BASE/api/mix/download" --output mix_output.wav
echo "→ mix_output.wav salvo ($(du -h mix_output.wav | cut -f1))"

echo -e "\n═══════════════════════════════════════"
echo "  ✓ Testes concluídos"
echo "═══════════════════════════════════════"
