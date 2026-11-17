"""Memoria de las conversaciones (checkpointer del grafo).

Con DATABASE_URL se guarda en Postgres (PostgresSaver): sobrevive a reinicios y despliegues.
Sin DATABASE_URL, o si la base no responde al arrancar, queda en RAM (MemorySaver) y la app sigue funcionando.
"""
import psycopg
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from src.router import db


def crear_checkpointer() -> tuple[MemorySaver | PostgresSaver, str]:
    """Devuelve (checkpointer, descripción) para mostrar en los logs y en /health."""
    if not db.activa():
        return MemorySaver(), "ram"
    try:
        saver = PostgresSaver(db.pool())
        saver.setup()  # crea sus tablas si no existen (idempotente)
        return saver, "postgres"
    except psycopg.Error:
        db.log.exception("Postgres no respondió al arrancar: la memoria queda en RAM (se pierde al reiniciar)")
        return MemorySaver(), "ram (Postgres no respondió)"
