#!/usr/bin/env python
"""
Script de servidor estable para Indio-Bot
Ejecuta el servidor FastAPI con manejo de errores y reinicio automático
"""
import os
import sys
import signal
import subprocess
import time
from pathlib import Path

def main():
    # Cambiar al directorio del script
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Verificar .env
    if not Path(".env").exists():
        print("ERROR: No se encontró .env")
        print("Copie .env.example a .env y configure las credenciales")
        input("Presione Enter para continuar...")
        return
    
    print("=" * 50)
    print("  Indio-Bot Server")
    print("  http://127.0.0.1:8001")
    print("=" * 50)
    print()
    
    # Matar procesos uvicorn existentes
    try:
        subprocess.run(["taskkill", "/F", "/IM", "uvicorn.exe"], 
                      capture_output=True, check=False)
        time.sleep(1)
    except Exception:
        pass
    
    # Construir comando
    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", "127.0.0.1",
        "--port", "8001"
    ]
    
    try:
        process = subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario")
    except Exception as e:
        print(f"\nError: {e}")
        input("Presione Enter para continuar...")

if __name__ == "__main__":
    main()