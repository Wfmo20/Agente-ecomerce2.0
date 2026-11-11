"""Pruebas de la API sin llamar al modelo ni a Telegram (el grafo y sendMessage se reemplazan)."""
import pytest
from fastapi.testclient import TestClient

import api.app as app_mod

SECRETO = "secreto-de-prueba"


class GrafoFalso:
    def __init__(self, falla=False):
        self.falla = falla
        self.llamadas = []

    def invoke(self, entrada, config):
        self.llamadas.append((entrada, config))
        if self.falla:
            raise RuntimeError("API key not valid: AIza-clave-que-no-debe-salir")
        return {"ruta": "postventa", "motivo": "Habla de un pedido.", "respuesta": "Soy el agente de postventa."}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    enviados = []
    monkeypatch.setattr(app_mod, "enviar_a_telegram", lambda chat_id, texto: enviados.append((chat_id, texto)))
    with TestClient(app_mod.app) as c:
        c.enviados = enviados
        yield c


def update(texto="mi pedido 4521 llegó roto", chat_id=111):
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": texto}}


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_chat_sin_texto_da_422(cliente):
    assert cliente.post("/chat", json={"user_id": "x"}).status_code == 422


def test_chat_modelo_falla_da_502_sin_filtrar_detalles(cliente):
    cliente.app.state.grafo = GrafoFalso(falla=True)
    r = cliente.post("/chat", json={"user_id": "x", "texto": "hola"})
    assert r.status_code == 502
    assert "AIza" not in r.text and "Traceback" not in r.text


@pytest.mark.parametrize("cabeceras", [{}, {"X-Telegram-Bot-Api-Secret-Token": "otro"}])
def test_telegram_secreto_invalido_da_403(cliente, cabeceras):
    cliente.app.state.grafo = GrafoFalso()
    r = cliente.post("/telegram", json=update(), headers=cabeceras)
    assert r.status_code == 403
    assert cliente.enviados == [] and cliente.app.state.grafo.llamadas == []


def test_telegram_responde_al_chat(cliente):
    cliente.app.state.grafo = grafo = GrafoFalso()
    r = cliente.post("/telegram", json=update(), headers={"X-Telegram-Bot-Api-Secret-Token": SECRETO})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert grafo.llamadas[0][1]["configurable"]["thread_id"] == "111"
    assert cliente.enviados == [(111, "Soy el agente de postventa.")]


def test_telegram_ignora_updates_sin_texto(cliente):
    cliente.app.state.grafo = grafo = GrafoFalso()
    sticker = {"update_id": 2, "message": {"chat": {"id": 111}, "sticker": {}}}
    r = cliente.post("/telegram", json=sticker, headers={"X-Telegram-Bot-Api-Secret-Token": SECRETO})
    assert r.status_code == 200 and grafo.llamadas == [] and cliente.enviados == []


def test_telegram_modelo_falla_igual_da_200_y_avisa(cliente):
    cliente.app.state.grafo = GrafoFalso(falla=True)
    r = cliente.post("/telegram", json=update(), headers={"X-Telegram-Bot-Api-Secret-Token": SECRETO})
    assert r.status_code == 200
    assert "problema" in cliente.enviados[0][1] and "AIza" not in cliente.enviados[0][1]
