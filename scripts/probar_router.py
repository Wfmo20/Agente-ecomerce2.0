"""Pasa los 6 mensajes de ejemplo por el router y muestra la ruta de cada uno.

    python scripts/probar_router.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.router.graph import graph  # noqa: E402

MENSAJES = [
    "¿tienen la polera azul en talla M?",
    "mi pedido 4521 llegó roto",
    "hola",
    "¿cuánto cuesta el envío a Valparaíso?",
    "quiero devolver unas zapatillas",
    "¿qué hora es en Tokio?",
]

for mensaje in MENSAJES:
    estado = graph.invoke({"mensaje": mensaje}, {"configurable": {"thread_id": str(uuid.uuid4())}})
    print(f"{estado['ruta']:<10} {mensaje}\n           motivo: {estado['motivo']}")
