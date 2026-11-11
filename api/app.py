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
from fastapi import Body, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODELO = os.environ.get("MODELO", "gemini-3.5-flash-lite")
log = logging.getLogger("uvicorn.error")
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

La conversación se recuerda por `user_id` (cada usuario tiene su propio hilo de memoria).
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
        description="Mensaje que escribió el cliente.",
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
        examples=[
            "Soy el agente de preventa. Recibí: ¿tienen la polera azul en talla M?. "
            "Pronto podré ayudarte con productos y compras."
        ],
    )


class ErrorResponse(BaseModel):
    detail: str = Field(
        description="Mensaje de error para el cliente (sin detalles internos).",
        examples=["El modelo no respondió. Intenta de nuevo en unos segundos."],
    )


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
    responses={
        200: {"description": "El router clasificó el mensaje y el agente destino respondió."},
        422: {"description": "Body inválido: falta `user_id` o `texto`, o vienen vacíos."},
        502: {"model": ErrorResponse, "description": "El modelo de lenguaje falló o no respondió."},
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
    return ChatResponse(ruta=estado["ruta"], motivo=estado["motivo"], respuesta=estado["respuesta"])


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


@app.post("/telegram", tags=["telegram"], include_in_schema=False)
def telegram(
    request: Request,
    update: dict[str, Any] = Body(default_factory=dict),
    secreto: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    # Solo Telegram conoce el secreto (se lo dimos en setWebhook): si no coincide, no viene de Telegram.
    esperado = os.environ.get("TELEGRAM_SECRET", "")
    if not esperado or not secreto or not hmac.compare_digest(secreto.encode(), esperado.encode()):
        raise HTTPException(status_code=403, detail="Secreto de Telegram inválido.")

    mensaje = update.get("message") or {}
    texto = mensaje.get("text")
    chat_id = (mensaje.get("chat") or {}).get("id")
    if not texto or chat_id is None:
        # Stickers, fotos, ediciones, etc.: se ignoran. Se responde 200 para que Telegram no reintente.
        return {"ok": True}

    config = {"configurable": {"thread_id": str(chat_id)}}
    try:
        estado = request.app.state.grafo.invoke({"mensaje": texto}, config)
        respuesta = estado["respuesta"]
        log.info("Telegram chat_id=%s → ruta=%s · motivo: %s", chat_id, estado["ruta"], estado["motivo"])
    except Exception:
        log.exception("Falló el grafo router para el chat de Telegram %s", chat_id)
        respuesta = "Tuve un problema para responderte. Intenta de nuevo en unos segundos."

    enviar_a_telegram(chat_id, respuesta)
    # 200 siempre (salvo secreto inválido): si no, Telegram reintenta el mismo update.
    return {"ok": True}
