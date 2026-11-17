"""Conexión a Postgres (DATABASE_URL): memoria de conversaciones, catálogo y solicitudes de postventa.

Sin DATABASE_URL el proyecto funciona igual que antes: memoria en RAM y catálogo desde datos/catalogo.json
(así corren las pruebas y el modo local sin base de datos).
"""
import json
import logging
import os
import threading
import unicodedata
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger("uvicorn.error")
DATOS = Path(__file__).resolve().parent / "datos"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id        text PRIMARY KEY,
    nombre    text NOT NULL,
    categoria text NOT NULL,
    precio    integer NOT NULL,
    busqueda  text NOT NULL            -- nombre, categoría y colores en minúsculas y sin tildes
);
CREATE TABLE IF NOT EXISTS stock (
    producto_id text NOT NULL REFERENCES productos(id),
    color       text NOT NULL,
    talla       text NOT NULL,
    unidades    integer NOT NULL CHECK (unidades >= 0),
    orden       integer NOT NULL,      -- respeta el orden de colores y tallas del catálogo original
    PRIMARY KEY (producto_id, color, talla)
);
CREATE TABLE IF NOT EXISTS solicitudes (
    id       serial PRIMARY KEY,       -- único aunque lleguen dos solicitudes a la vez
    tipo     text NOT NULL,
    pedido   text NOT NULL,
    producto text NOT NULL,
    motivo   text NOT NULL,
    estado   text NOT NULL DEFAULT 'registrada',
    creada   timestamptz NOT NULL DEFAULT now()
);
"""

_pool: ConnectionPool | None = None
_listo = False
_lock = threading.Lock()


def norm(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Valparaíso' con 'valparaiso'."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def activa() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def pool() -> ConnectionPool:
    """Pool de conexiones (se abre al primer uso). Crea las tablas y carga el catálogo si faltan."""
    global _pool, _listo
    with _lock:
        if _pool is None:
            # autocommit + dict_row: lo que exige PostgresSaver, y cómodo para las demás consultas.
            _pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5, timeout=5, open=False,
                                   kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
            _pool.open(wait=False)
        if not _listo:
            _preparar(_pool)  # si la base no responde, lanza y se reintenta en el próximo uso
            _listo = True
    return _pool


def _preparar(p: ConnectionPool) -> None:
    catalogo = json.loads((DATOS / "catalogo.json").read_text(encoding="utf-8"))
    with p.connection() as conn:
        for sentencia in filter(str.strip, ESQUEMA.split(";")):  # de a una: con prepare_threshold=0 no se admiten varias
            conn.execute(sentencia)
        # Carga inicial desde el JSON. ON CONFLICT DO NOTHING: no pisa lo que se haya editado en la base.
        for prod in catalogo["productos"]:
            busqueda = norm(f"{prod['nombre']} {prod['categoria']} {' '.join(prod['stock'])}")
            conn.execute("INSERT INTO productos (id, nombre, categoria, precio, busqueda) VALUES (%s, %s, %s, %s, %s) "
                         "ON CONFLICT (id) DO NOTHING",
                         (prod["id"], prod["nombre"], prod["categoria"], prod["precio"], busqueda))
            filas = [(prod["id"], color, talla, n, i)
                     for i, (color, talla, n) in enumerate((c, t, n) for c, ts in prod["stock"].items() for t, n in ts.items())]
            with conn.cursor() as cur:
                cur.executemany("INSERT INTO stock (producto_id, color, talla, unidades, orden) VALUES (%s, %s, %s, %s, %s) "
                                "ON CONFLICT DO NOTHING", filas)
    log.info("Postgres listo: tablas creadas y catálogo cargado")


def cerrar() -> None:
    global _pool, _listo
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool, _listo = None, False
