"""Pruebas de punta a punta con el modelo real: el agente usa sus herramientas y conserva cifras y condiciones."""
import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
pytestmark = pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="Falta GOOGLE_API_KEY en .env")


def conversar(*mensajes):
    from src.router.graph import graph

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    return [graph.invoke({"mensaje": m}, config) for m in mensajes][-1]


def test_preventa_stock_real():
    e = conversar("¿tienen la polera básica azul en talla M?")
    assert e["ruta"] == "preventa"
    assert any(h.startswith("consultar_stock") for h in e["herramientas"])
    assert "agotad" in e["respuesta"].lower() or "no tenemos" in e["respuesta"].lower()


def test_preventa_envio_conserva_cifras():
    e = conversar("¿cuánto cuesta el envío a Valparaíso?")
    assert "$4.990" in e["respuesta"] and "2 a 3 días hábiles" in e["respuesta"]


def test_postventa_pide_numero_de_pedido():
    e = conversar("quiero devolver unas zapatillas")
    assert e["ruta"] == "postventa" and not e["herramientas"]
    assert "pedido" in e["respuesta"].lower()


def test_postventa_estado_del_pedido():
    e = conversar("¿en qué va mi pedido 4530?")
    assert "consultar_pedido(numero_pedido='4530')" in e["herramientas"]
    assert "camino" in e["respuesta"].lower() and "CHX-88457" in e["respuesta"]


def test_postventa_pregunta_producto_antes_de_registrar():
    e = conversar("mi pedido 4521 llegó roto")
    assert not any(h.startswith("registrar_solicitud") for h in e["herramientas"])
    e2 = conversar("mi pedido 4521 llegó roto", "las zapatillas")
    assert any(h.startswith("registrar_solicitud") for h in e2["herramientas"])
    assert "SOL-" in e2["respuesta"]
