import os
import sys
from fastapi.testclient import TestClient

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from backend.app import app

client = TestClient(app)

def test_api():
    print("=== Testando API FastAPI do AutoShorts ===")
    
    # 1. Testa rota raiz / frontend
    res_root = client.get("/")
    assert res_root.status_code == 200, f"Erro na rota raiz: {res_root.status_code}"
    assert "AutoShorts" in res_root.text, "Título AutoShorts não encontrado no HTML"
    print("[OK] Rota raiz (Frontend UI): 200 OK")

    # 2. Testa listagem de outputs
    res_outputs = client.get("/api/outputs")
    assert res_outputs.status_code == 200, f"Erro na rota /api/outputs: {res_outputs.status_code}"
    outputs = res_outputs.json()
    print(f"[OK] Rota /api/outputs retornou {len(outputs)} vídeos na biblioteca")

    print("\n✅ API FastAPI validada com sucesso!")

if __name__ == "__main__":
    test_api()
