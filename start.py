import os
import sys
import signal

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import webbrowser
import threading
import time
import uvicorn


def open_browser():
    time.sleep(1.5)
    print("\n[AutoShorts AI] Abrindo interface: http://localhost:8000")
    webbrowser.open("http://localhost:8000")


def shutdown_handler(signum, frame):
    print("\n[AutoShorts AI] Encerrando servidor...")
    sys.exit(0)


if __name__ == "__main__":
    print("=" * 65)
    print(" AutoShorts AI v2.0 - Gerador de Shorts Inteligente")
    print(" 100% Gratuito | Legendas Animadas | Marca d'Agua | 9:16")
    print("=" * 65)

    signal.signal(signal.SIGINT, shutdown_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown_handler)

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
