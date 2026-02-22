"""
DJMIX Launcher — Entry point for desktop app.

Starts FastAPI server and opens browser automatically.
Usage: python launcher.py [--port 8000] [--no-browser]
"""

import uvicorn
import webbrowser
import threading
import argparse
import sys
import os

VERSION = "3.3.0"

# Ensure backend dir is in path
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Frontend build dir
FRONTEND_BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "build")


def open_browser(port, delay=2.0):
    """Open browser after a short delay to let server start."""
    import time
    time.sleep(delay)
    url = f"http://localhost:{port}"
    print(f"\n  DJMIX aberto em {url}")
    print(f"  Ctrl+C para encerrar\n")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="DJMIX Desktop App")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor")
    parser.add_argument("--no-browser", action="store_true", help="Nao abrir browser")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor")
    args = parser.parse_args()

    print("=" * 50)
    print(f"  DJMIX v{VERSION}")
    print("=" * 50)

    # Verificar se frontend build existe
    if not os.path.isdir(FRONTEND_BUILD):
        print()
        print("  Frontend nao buildado!")
        print("  Execute: make install")
        print("  Ou:      cd frontend && npm install && npm run build")
        print()
        sys.exit(1)

    if not args.no_browser:
        threading.Thread(
            target=open_browser,
            args=(args.port,),
            daemon=True,
        ).start()

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        log_level="warning",
        app_dir=BACKEND_DIR,
    )


if __name__ == "__main__":
    main()
