"""Pruebas del router con los 15 casos de casos_router.json.

El modelo no es determinista: cada caso fallado se marca XFAIL (no rompe la suite)
y test_umbral_de_aciertos exige al menos 13 de 15.
"""
import json
import os
import uuid
from functools import cache
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CASOS = json.loads((Path(__file__).parent / "casos_router.json").read_text(encoding="utf-8"))
MINIMO = 13

pytestmark = pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="Falta GOOGLE_API_KEY en .env")


@cache
def ruta_de(mensaje: str) -> str:
    """Ruta que elige el router (cacheada: cada caso llama al modelo una sola vez)."""
    from src.router.graph import graph

    estado = graph.invoke({"mensaje": mensaje}, {"configurable": {"thread_id": str(uuid.uuid4())}})
    return estado["ruta"]


@pytest.mark.parametrize("caso", CASOS, ids=[c["mensaje"] for c in CASOS])
def test_caso(caso):
    obtenido = ruta_de(caso["mensaje"])
    if obtenido != caso["esperado"]:
        pytest.xfail(f"esperado {caso['esperado']}, obtenido {obtenido}")


def test_umbral_de_aciertos():
    aciertos = sum(ruta_de(c["mensaje"]) == c["esperado"] for c in CASOS)
    assert aciertos >= MINIMO, f"El router acertó {aciertos}/{len(CASOS)}; se exigen al menos {MINIMO}."
