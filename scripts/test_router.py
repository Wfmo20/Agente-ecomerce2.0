"""Corre los 15 casos de tests/casos_router.json y muestra esperado vs obtenido.

    python scripts/test_router.py
"""
import json
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.router.graph import graph  # noqa: E402

casos = json.loads((RAIZ / "tests" / "casos_router.json").read_text(encoding="utf-8"))

print(f"{'mensaje':<62} {'esperado':<10} {'obtenido':<10}    motivo")
print("-" * 130)
fallados = []
for caso in casos:
    try:
        estado = graph.invoke({"mensaje": caso["mensaje"]}, {"configurable": {"thread_id": str(uuid.uuid4())}})
        obtenido, motivo = estado["ruta"], estado["motivo"]
    except Exception as error:  # el modelo falló: cuenta como fallo, sin cortar la tabla
        obtenido, motivo = "ERROR", f"{type(error).__name__}: {error}"[:120]
    ok = obtenido == caso["esperado"]
    if not ok:
        fallados.append((caso, obtenido))
    print(f"{caso['mensaje']:<62} {caso['esperado']:<10} {obtenido:<10} {'✔' if ok else '✘'}  {motivo}")

aciertos = len(casos) - len(fallados)
print("-" * 130)
print(f"Aciertos: {aciertos}/{len(casos)} ({aciertos / len(casos):.0%})")
if fallados:
    print("\nFallados:")
    for caso, obtenido in fallados:
        print(f"  ✘ {caso['mensaje']!r}: esperado {caso['esperado']}, obtenido {obtenido}")
