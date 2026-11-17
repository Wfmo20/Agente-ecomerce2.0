"""Pruebas contra un Postgres real (sin modelo): catálogo, solicitudes, memoria y caída de la base.

Usan TEST_DATABASE_URL (una base de pruebas, NO la de Render), ej.:
    TEST_DATABASE_URL=postgresql://postgres@localhost:5433/ecommerce_test pytest tests/test_postgres.py -v
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from langchain_core.messages import HumanMessage

from src.router import db, graph, tools

URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="Falta TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def base(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    db.cerrar()
    yield
    db.cerrar()
    graph._cache.pop("graph", None)  # quedó con el pool cerrado: se vuelve a compilar si otra prueba lo pide


def test_catalogo_se_carga_y_busca_igual_que_el_json(monkeypatch):
    en_postgres = tools.buscar_productos.invoke({"consulta": "poleras"})
    monkeypatch.delenv("DATABASE_URL")
    en_json = tools.buscar_productos.invoke({"consulta": "poleras"})
    assert en_postgres and sorted(en_postgres, key=lambda p: p["id"]) == sorted(en_json, key=lambda p: p["id"])


def test_stock_desde_postgres():
    r = tools.consultar_stock.invoke({"producto_id": "pol-001", "color": "azul", "talla": "M"})
    assert r["stock_unidades"] == {"azul": {"M": 0}}


def test_busqueda_no_interpreta_comodines_ni_sql():
    for consulta in ["%%%", "___", "'; DROP TABLE productos; --"]:
        assert tools.buscar_productos.invoke({"consulta": consulta}) == []
    assert tools.buscar_productos.invoke({"consulta": "polera"})  # la tabla sigue ahí


def test_solicitudes_con_numero_unico_en_paralelo():
    args = {"numero_pedido": "4521", "tipo": "reclamo", "producto": "ZAP-010", "motivo": "llegó roto"}
    with ThreadPoolExecutor(8) as ex:
        casos = [r["caso"] for r in ex.map(lambda _: tools.registrar_solicitud.invoke(args), range(16))]
    assert len(set(casos)) == 16 and all(c.startswith("SOL-") for c in casos)


def test_memoria_en_postgres_sobrevive_a_un_reinicio():
    from src.router.graph import compilar
    from src.router.memoria import crear_checkpointer

    config = {"configurable": {"thread_id": f"prueba-{uuid.uuid4()}"}}
    saver, tipo = crear_checkpointer()
    assert tipo == "postgres"
    compilar(saver).update_state(config, {"ruta": "generica", "messages": [HumanMessage("hola, soy Ana")]},
                              as_node="respuesta_generica")
    db.cerrar()  # "reinicio": pool y grafo nuevos
    estado = compilar(crear_checkpointer()[0]).get_state(config).values
    assert estado["messages"][0].content == "hola, soy Ana"


def test_si_la_base_no_responde_nada_se_cae(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nadie@127.0.0.1:1/nada?connect_timeout=1")
    from src.router.memoria import crear_checkpointer

    assert crear_checkpointer()[1].startswith("ram")
    assert tools.buscar_productos.invoke({"consulta": "polera"}) == [tools.CATALOGO_NO_DISPONIBLE]
    assert tools.consultar_stock.invoke({"producto_id": "POL-001"}) == tools.CATALOGO_NO_DISPONIBLE
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4521", "tipo": "reclamo", "producto": "ZAP-010",
                                          "motivo": "llegó roto"})
    assert "no se pudo registrar" in r["error"].lower()
