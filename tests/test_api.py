"""Pruebas de la API sin llamar al modelo ni a Telegram (el grafo y sendMessage se reemplazan)."""
import pytest
from fastapi.testclient import TestClient

import api.app as app_mod

SECRETO = "secreto-de-prueba"
CLAVE = "clave-de-prueba"
AUTORIZADO = 111
NO_AUTORIZADO = 999


class GrafoFalso:
    def __init__(self, falla=False):
        self.falla = falla
        self.llamadas = []

    def invoke(self, entrada, config):
        self.llamadas.append((entrada, config))
        if self.falla:
            raise RuntimeError("API key not valid: AIza-clave-que-no-debe-salir")
        return {"ruta": "postventa", "motivo": "Habla de un pedido.", "respuesta": "Soy el agente de postventa.",
                "herramientas": ["consultar_pedido(numero_pedido='4521')"]}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    monkeypatch.setenv("API_KEY", CLAVE)
    monkeypatch.setenv("TELEGRAM_ALLOWED_IDS", f"{AUTORIZADO}, 222")
    enviados = []
    monkeypatch.setattr(app_mod, "enviar_a_telegram", lambda chat_id, texto: enviados.append((chat_id, texto)))
    with TestClient(app_mod.app) as c:
        c.enviados = enviados
        c.app.state.grafo = GrafoFalso()
        yield c


def update(texto="mi pedido 4521 llegó roto", chat_id=AUTORIZADO):
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": texto}}


TG = {"X-Telegram-Bot-Api-Secret-Token": SECRETO}
API = {"X-API-Key": CLAVE}


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


# ---------- /chat ----------

def test_chat_con_clave_responde(cliente):
    r = cliente.post("/chat", json={"user_id": "x", "texto": "mi pedido 4521"}, headers=API)
    assert r.status_code == 200
    assert r.json()["ruta"] == "postventa" and r.json()["herramientas"]


@pytest.mark.parametrize("cabeceras", [{}, {"X-API-Key": "otra"}])
def test_chat_sin_clave_valida_da_401_y_no_llama_al_modelo(cliente, cabeceras):
    r = cliente.post("/chat", json={"user_id": "x", "texto": "hola"}, headers=cabeceras)
    assert r.status_code == 401 and cliente.app.state.grafo.llamadas == []


def test_chat_sin_api_key_configurada_da_503(cliente, monkeypatch):
    monkeypatch.delenv("API_KEY")
    r = cliente.post("/chat", json={"user_id": "x", "texto": "hola"}, headers={"X-API-Key": ""})
    assert r.status_code == 503


@pytest.mark.parametrize("cuerpo", [{"user_id": "x"}, {"user_id": "x", "texto": ""}, {"user_id": "x", "texto": "a" * 1001}])
def test_chat_body_invalido_da_422(cliente, cuerpo):
    assert cliente.post("/chat", json=cuerpo, headers=API).status_code == 422


def test_chat_modelo_falla_da_502_sin_filtrar_detalles(cliente):
    cliente.app.state.grafo = GrafoFalso(falla=True)
    r = cliente.post("/chat", json={"user_id": "x", "texto": "hola"}, headers=API)
    assert r.status_code == 502
    assert "AIza" not in r.text and "Traceback" not in r.text


# ---------- /telegram ----------

@pytest.mark.parametrize("cabeceras", [{}, {"X-Telegram-Bot-Api-Secret-Token": "otro"}])
def test_telegram_secreto_invalido_da_403(cliente, cabeceras):
    r = cliente.post("/telegram", json=update(), headers=cabeceras)
    assert r.status_code == 403
    assert cliente.enviados == [] and cliente.app.state.grafo.llamadas == []


def test_telegram_responde_al_chat_autorizado(cliente):
    r = cliente.post("/telegram", json=update(), headers=TG)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert cliente.app.state.grafo.llamadas[0][1]["configurable"]["thread_id"] == f"telegram-{AUTORIZADO}"
    assert cliente.enviados == [(AUTORIZADO, "Soy el agente de postventa.")]


def test_telegram_chat_no_autorizado_se_rechaza(cliente):
    r = cliente.post("/telegram", json=update(chat_id=NO_AUTORIZADO), headers=TG)
    assert r.status_code == 200
    assert cliente.app.state.grafo.llamadas == []
    assert cliente.enviados[0][0] == NO_AUTORIZADO and "No estás autorizado" in cliente.enviados[0][1]
    assert str(NO_AUTORIZADO) in cliente.enviados[0][1]


def test_telegram_ignora_updates_sin_texto(cliente):
    sticker = {"update_id": 2, "message": {"chat": {"id": AUTORIZADO}, "sticker": {}}}
    r = cliente.post("/telegram", json=sticker, headers=TG)
    assert r.status_code == 200 and cliente.app.state.grafo.llamadas == [] and cliente.enviados == []


def test_telegram_mensaje_muy_largo(cliente):
    r = cliente.post("/telegram", json=update(texto="a" * 1500), headers=TG)
    assert r.status_code == 200 and cliente.app.state.grafo.llamadas == []
    assert "muy largo" in cliente.enviados[0][1]


def test_telegram_modelo_falla_igual_da_200_y_avisa(cliente):
    cliente.app.state.grafo = GrafoFalso(falla=True)
    r = cliente.post("/telegram", json=update(), headers=TG)
    assert r.status_code == 200
    assert "problema" in cliente.enviados[0][1] and "AIza" not in cliente.enviados[0][1]
