"""Pruebas del router con los 18 casos de casos_router.json.

Los casos con "historial" son respuestas cortas de seguimiento ("la negra", "4521"): antes se envían los mensajes
del historial en la misma conversación y se evalúa la ruta del último.
El modelo no es determinista: cada caso fallado se marca XFAIL (no rompe la suite)
y test_umbral_de_aciertos exige al menos 16 de 18.
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
MINIMO = 16

pytestmark = pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="Falta GOOGLE_API_KEY en .env")


@cache
def ruta_de(mensaje: str, historial: tuple[str, ...] = ()) -> str:
    """Ruta que elige el router para el último mensaje (cacheada: cada caso se evalúa una sola vez)."""
    from src.router.graph import graph

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    for previo in historial:
        graph.invoke({"mensaje": previo}, config)
    return graph.invoke({"mensaje": mensaje}, config)["ruta"]


def ruta_del_caso(caso: dict) -> str:
    return ruta_de(caso["mensaje"], tuple(caso.get("historial", [])))


@pytest.mark.parametrize("caso", CASOS, ids=[" → ".join([*c.get("historial", []), c["mensaje"]]) for c in CASOS])
def test_caso(caso):
    obtenido = ruta_del_caso(caso)
    if obtenido != caso["esperado"]:
        pytest.xfail(f"esperado {caso['esperado']}, obtenido {obtenido}")


def test_umbral_de_aciertos():
    aciertos = sum(ruta_del_caso(c) == c["esperado"] for c in CASOS)
    assert aciertos >= MINIMO, f"El router acertó {aciertos}/{len(CASOS)}; se exigen al menos {MINIMO}."
