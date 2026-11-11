"""API del chat de un ecommerce: expone el agente router por HTTP.

Levantar (desde la raíz):  uvicorn api.app:app --reload --port 8000
Documentación interactiva:  http://localhost:8000/docs
"""
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODELO = os.environ.get("MODELO", "gemini-3.5-flash-lite")
log = logging.getLogger("uvicorn.error")
LARGO_MAXIMO = 1000  # caracteres por mensaje: acota costo y abuso
# httpx registra cada URL en nivel INFO, y la de Telegram lleva el token: se silencia.
logging.getLogger("httpx").setLevel(logging.WARNING)

DESCRIPCION = """
API del **chat de una tienda online**. Cada mensaje pasa por un **router** (LangGraph + Gemini)
que decide a qué agente va:

| Ruta | Cuándo |
|---|---|
| `preventa` | Quiere comprar o pregunta por productos, precios, tallas, stock, promociones, envío o formas de pago. |
| `postventa` | Ya compró: reclamo, seguimiento de un pedido, devolución, cambio, garantía o producto dañado. |
| `generica` | No tiene que ver con la tienda (clima, chistes, hora…) o es un saludo sin pedido. |

Preventa y postventa responden con Gemini y herramientas sobre un **catálogo y pedidos de prueba**
(no inventan precios, stock ni estados). La conversación se recuerda por `user_id`.

**Acceso:** `/chat` exige la cabecera `X-API-Key` con el valor de `API_KEY` (botón **Authorize** arriba a la derecha).
"""

TAGS = [
    {"name": "salud", "description": "Revisar que la API está arriba y qué modelo usa."},
    {"name": "chat", "description": "Enviar un mensaje del cliente y obtener la ruta, el motivo y la respuesta."},
    {"name": "telegram", "description": "Webhook de Telegram: verifica el secreto, pasa el texto por el router y le contesta al usuario."},
]


# ---------- Modelos de entrada y salida ----------

class HealthResponse(BaseModel):
    ok: bool = Field(description="True si la API está funcionando.", examples=[True])
    modelo: str = Field(description="Modelo de lenguaje que usa el router.", examples=["gemini-3.5-flash-lite"])


class ChatRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        description="Identificador del cliente. Se usa como thread_id: mismo user_id = misma conversación.",
        examples=["cliente-123"],
    )
    texto: str = Field(
        min_length=1,
        max_length=LARGO_MAXIMO,
        description=f"Mensaje que escribió el cliente (máximo {LARGO_MAXIMO} caracteres).",
        examples=["¿tienen la polera azul en talla M?"],
    )


class ChatResponse(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="Agente al que el router envió el mensaje.", examples=["preventa"]
    )
    motivo: str = Field(
        description="Una frase del router explicando por qué eligió esa ruta.",
        examples=["El cliente pregunta por la disponibilidad de un producto y su talla antes de comprar."],
    )
    respuesta: str = Field(
        description="Respuesta del agente destino para el cliente.",
        examples=["Tenemos la Polera deportiva dry-fit azul en talla M ($17.990) con 9 unidades. La básica azul M está agotada."],
    )
    herramientas: list[str] = Field(
        description="Herramientas que usó el agente, con sus argumentos (trazabilidad).",
        examples=[["buscar_productos(consulta='polera')", "consultar_stock(producto_id='POL-001', color='azul', talla='M')"]],
    )


class ErrorResponse(BaseModel):
    detail: str = Field(
        description="Mensaje de error para el cliente (sin detalles internos).",
        examples=["El modelo no respondió. Intenta de nuevo en unos segundos."],
    )


# ---------- Acceso ----------

_api_key = APIKeyHeader(name="X-API-Key", auto_error=False, description="Valor de API_KEY del servidor.")


def verificar_api_key(clave: str | None = Depends(_api_key)) -> None:
    """Valida X-API-Key contra API_KEY (comparación en tiempo constante). Sin API_KEY configurada, nadie entra."""
    esperada = os.environ.get("API_KEY", "")
    if not esperada:
        log.error("API_KEY no está configurada: /chat rechaza todo")
        raise HTTPException(status_code=503, detail="El servicio no tiene configurado el acceso (API_KEY).")
    if not clave or not hmac.compare_digest(clave.encode(), esperada.encode()):
        log.warning("Acceso rechazado a /chat (X-API-Key %s)", "ausente" if not clave else "incorrecta")
        raise HTTPException(status_code=401, detail="Falta X-API-Key o no es válida.")


def chats_autorizados() -> set[str]:
    """chat_id de Telegram autorizados (TELEGRAM_ALLOWED_IDS, separados por coma)."""
    return {c.strip() for c in os.environ.get("TELEGRAM_ALLOWED_IDS", "").split(",") if c.strip()}


# ---------- App ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # El grafo se compila UNA sola vez, al arrancar la app (no en cada request).
    from src.router.graph import graph

    app.state.grafo = graph
    log.info("Grafo router listo (modelo %s)", MODELO)
    yield


app = FastAPI(
    title="Ecommerce Router API",
    version="0.1.0",
    description=DESCRIPCION,
    openapi_tags=TAGS,
    lifespan=lifespan,
)


@app.get("/health", tags=["salud"], response_model=HealthResponse, summary="Estado de la API")
def health() -> HealthResponse:
    return HealthResponse(ok=True, modelo=MODELO)


@app.post(
    "/chat",
    tags=["chat"],
    response_model=ChatResponse,
    summary="Enviar un mensaje al router",
    dependencies=[Depends(verificar_api_key)],
    responses={
        200: {"description": "El router clasificó el mensaje y el agente destino respondió."},
        401: {"model": ErrorResponse, "description": "Falta la cabecera `X-API-Key` o no es válida."},
        422: {"description": "Body inválido: falta `user_id` o `texto`, vienen vacíos o el texto es demasiado largo."},
        502: {"model": ErrorResponse, "description": "El modelo de lenguaje falló o no respondió."},
        503: {"model": ErrorResponse, "description": "El servidor no tiene `API_KEY` configurada."},
    },
)
def chat(pedido: ChatRequest, request: Request) -> ChatResponse:
    config = {"configurable": {"thread_id": pedido.user_id}}
    try:
        estado = request.app.state.grafo.invoke({"mensaje": pedido.texto}, config)
    except Exception:
        # El detalle (stack trace) queda solo en el log del servidor, nunca en la respuesta.
        log.exception("Falló el grafo router para user_id=%s", pedido.user_id)
        raise HTTPException(status_code=502, detail="El modelo no respondió. Intenta de nuevo en unos segundos.")
    log.info("/chat user_id=%s → ruta=%s · motivo: %s", pedido.user_id, estado["ruta"], estado["motivo"])
    return ChatResponse(ruta=estado["ruta"], motivo=estado["motivo"], respuesta=estado["respuesta"],
                        herramientas=estado.get("herramientas") or [])


def enviar_a_telegram(chat_id: int, texto: str) -> None:
    """Le contesta al usuario en Telegram (sendMessage de la Bot API)."""
    token = os.environ.get("TELEGRAM_TOKEN", "")
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto},
            timeout=15,
        )
        r.raise_for_status()
    except httpx.HTTPError:
        # No se loguea la excepción completa: su mensaje incluye la URL con el token.
        log.error("No se pudo enviar el mensaje a Telegram (chat_id=%s)", chat_id)


NO_AUTORIZADO = (
    "No estás autorizado para usar este bot. Tu chat_id es {chat_id}: pídele al administrador que lo agregue "
    "a TELEGRAM_ALLOWED_IDS."
)
MUY_LARGO = f"Tu mensaje es muy largo. Escríbeme tu consulta en menos de {LARGO_MAXIMO} caracteres."
FALLA_MODELO = "Tuve un problema para responderte (el modelo no respondió). Intenta de nuevo en unos segundos."


def atender_telegram(grafo, update: dict[str, Any], enviar=None) -> None:
    """Procesa un update de Telegram: autoriza el chat, pasa el texto por el router y contesta.

    La usan el webhook (/telegram) y el modo local por polling (scripts/bot_local.py).
    """
    enviar = enviar or enviar_a_telegram
    mensaje = update.get("message") or {}
    texto = mensaje.get("text")
    chat_id = (mensaje.get("chat") or {}).get("id")
    if not texto or chat_id is None:
        return  # stickers, fotos, ediciones, etc.: se ignoran

    if str(chat_id) not in chats_autorizados():
        log.warning("Telegram chat_id=%s rechazado (no está en TELEGRAM_ALLOWED_IDS)", chat_id)
        enviar(chat_id, NO_AUTORIZADO.format(chat_id=chat_id))
        return
    if texto.strip() == "/start":
        texto = "hola"
    if len(texto) > LARGO_MAXIMO:
        enviar(chat_id, MUY_LARGO)
        return

    config = {"configurable": {"thread_id": f"telegram-{chat_id}"}}
    try:
        estado = grafo.invoke({"mensaje": texto}, config)
        respuesta = estado["respuesta"]
        log.info("Telegram chat_id=%s → ruta=%s · motivo: %s", chat_id, estado["ruta"], estado["motivo"])
    except Exception:
        log.exception("Falló el grafo router para el chat de Telegram %s", chat_id)
        respuesta = FALLA_MODELO
    enviar(chat_id, respuesta[:4000])  # Telegram acepta hasta 4096 caracteres por mensaje


@app.post("/telegram", tags=["telegram"], include_in_schema=False)
def telegram(
    request: Request,
    update: dict[str, Any] = Body(default_factory=dict),
    secreto: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    # Solo Telegram conoce el secreto (se lo dimos en setWebhook): si no coincide, no viene de Telegram.
    esperado = os.environ.get("TELEGRAM_SECRET", "")
    if not esperado or not secreto or not hmac.compare_digest(secreto.encode(), esperado.encode()):
        log.warning("Webhook /telegram rechazado: secreto ausente o incorrecto")
        raise HTTPException(status_code=403, detail="Secreto de Telegram inválido.")

    atender_telegram(request.app.state.grafo, update, enviar_a_telegram)
    # 200 siempre (salvo secreto inválido): si no, Telegram reintenta el mismo update.
    return {"ok": True}
