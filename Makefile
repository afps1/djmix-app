.PHONY: install run dev build clean help

PYTHON = python3
VENV = backend/.venv
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn
LAUNCHER = $(VENV)/bin/python launcher.py

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Instala tudo (Python + Node + build frontend)
	@echo "=== Criando ambiente Python ==="
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	@echo ""
	@echo "=== Instalando dependencias Node ==="
	cd frontend && npm install
	@echo ""
	@echo "=== Buildando frontend ==="
	cd frontend && npm run build
	@echo ""
	@echo "✓ Instalacao completa! Execute: make run"

run: build ## Builda frontend e inicia o app
	@echo ""
	$(LAUNCHER)

dev: ## Inicia backend + frontend dev server (hot reload)
	@echo "Iniciando backend + frontend dev..."
	@$(UVICORN) server:app --port 8000 --reload --app-dir backend &
	@cd frontend && npm run dev &
	@echo ""
	@echo "Backend:  http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo "Ctrl+C para encerrar"
	@wait

build: ## Builda o frontend
	@cd frontend && npm run build 2>/dev/null || (echo "Execute 'make install' primeiro" && exit 1)

clean: ## Remove venv, node_modules e build
	rm -rf $(VENV)
	rm -rf frontend/node_modules
	rm -rf frontend/build
	@echo "✓ Limpo"
