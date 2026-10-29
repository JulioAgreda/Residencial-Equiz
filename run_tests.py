"""Ejecuta las pruebas de regresión entregadas como scripts independientes."""
from pathlib import Path
import subprocess, sys

base = Path(__file__).resolve().parent
scripts = sorted(base.glob("test_*.py"))
if not scripts:
    print("No se encontraron scripts test_*.py")
    raise SystemExit(2)
failed = []
for script in scripts:
    print(f"\n===== {script.name} =====", flush=True)
    result = subprocess.run([sys.executable, str(script)], cwd=base)
    if result.returncode:
        failed.append((script.name, result.returncode))
if failed:
    print("\nPRUEBAS FALLIDAS:")
    for name, code in failed:
        print(f"- {name}: código {code}")
    raise SystemExit(1)
print(f"\nRESULTADO: las {len(scripts)} pruebas finalizaron correctamente.")
