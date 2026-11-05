#!/usr/bin/env bash
# uruchom.sh - serwer transkrypcji gen 6 (uruchamiany z katalogu głównego repozytorium, np. przez uruchom_wsl.bat).
# Pierwszy raz: tworzy środowisko .venv i instaluje zależności (kilka minut, torch CPU ok. 200 MB); potem startuje od razu.
#   GUTAR_TOKEN=haslo PORT=8080 bash tools/gen6/server/uruchom.sh
set -e
cd "$(dirname "$0")/../../.."
PORT="${PORT:-8080}"
export GUTAR_TOKEN="${GUTAR_TOKEN:-gutar}"
if ! command -v python3 >/dev/null; then echo "Brak python3: sudo apt-get install -y python3 python3-venv python3-pip"; exit 1; fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv 2>/dev/null || { echo "Instaluję python3-venv (poprosi o hasło WSL)..."; sudo apt-get update -qq && sudo apt-get install -y python3-venv python3-pip; rm -rf .venv; python3 -m venv .venv; }
fi
. .venv/bin/activate
if ! python -c "import torch, fastapi, uvicorn, numpy" 2>/dev/null; then
  echo "Instaluję zależności (tylko za pierwszym razem)..."
  pip install -q --upgrade pip
  pip install -q --index-url https://download.pytorch.org/whl/cpu torch
  pip install -q numpy fastapi uvicorn
fi
echo
echo "Serwer: http://localhost:$PORT   (haslo/token: $GUTAR_TOKEN)   Zatrzymanie: Ctrl+C"
echo
exec python -m uvicorn tools.gen6.server.app:app --host 0.0.0.0 --port "$PORT"
