"""Agente router del chat de un ecommerce: decide si el mensaje va a preventa, postventa o generica,
y los agentes de preventa y postventa responden con herramientas sobre datos de prueba."""
import logging
import os
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.router import prompts, tools

# Solo el .env de la raíz del proyecto (sin buscar en carpetas superiores).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODELO = os.environ.get("MODELO", "gemini-3.5-flash-lite")
# Mensajes del historial que ven el router y los agentes (acota costo y largo del contexto).
HISTORIAL_MAX = 12
log = logging.getLogger("uvicorn.error")


class Decision(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(description="A qué agente va el mensaje.")
    motivo: str = Field(description="Una frase: por qué esa ruta.")


class Estado(TypedDict, total=False):
    mensaje: str
    ruta: str
    motivo: str
    respuesta: str
    herramientas: list[str]
    messages: Annotated[list[AnyMessage], add_messages]


_cache: dict = {}


def _modelo():
    """El modelo se crea al primer uso, así --diagrama funciona sin GOOGLE_API_KEY."""
    if "modelo" not in _cache:
        _cache["modelo"] = ChatGoogleGenerativeAI(model=MODELO, temperature=0, timeout=60, max_retries=1)
    return _cache["modelo"]


def _agente(nombre: str, prompt: str, herramientas: list):
    if nombre not in _cache:
        _cache[nombre] = create_agent(_modelo(), herramientas, system_prompt=prompt, name=nombre)
    return _cache[nombre]


def router(estado: Estado) -> dict:
    historial = estado.get("messages", [])[-HISTORIAL_MAX:]
    decision = _modelo().with_structured_output(Decision).invoke(
        [SystemMessage(prompts.ROUTER), *historial, HumanMessage(estado["mensaje"])]
    )
    return {
        "ruta": decision.ruta,
        "motivo": decision.motivo,
        "herramientas": [],
        "messages": [HumanMessage(estado["mensaje"])],
    }


def _atender(estado: Estado, nombre: str, prompt: str, herramientas: list) -> dict:
    """Corre el agente con sus herramientas y guarda en la memoria solo la respuesta final."""
    resultado = _agente(nombre, prompt, herramientas).invoke({"messages": estado["messages"][-HISTORIAL_MAX:]})
    usadas = [
        f"{llamada['name']}({', '.join(f'{k}={v!r}' for k, v in llamada['args'].items())})"
        for m in resultado["messages"] if isinstance(m, AIMessage) for llamada in m.tool_calls
    ]
    for u in usadas:
        log.info("%s → %s", nombre, u)
    texto = resultado["messages"][-1].text.strip() or "No pude generar una respuesta. ¿Puedes repetir tu consulta?"
    return {"respuesta": texto, "herramientas": usadas, "messages": [AIMessage(texto)]}


def agente_preventa(estado: Estado) -> dict:
    return _atender(estado, "agente_preventa", prompts.AGENTE_PREVENTA, tools.TOOLS_PREVENTA)


def agente_postventa(estado: Estado) -> dict:
    return _atender(estado, "agente_postventa", prompts.AGENTE_POSTVENTA, tools.TOOLS_POSTVENTA)


def respuesta_generica(estado: Estado) -> dict:
    return {"respuesta": prompts.RESPUESTA_GENERICA, "herramientas": [], "messages": [AIMessage(prompts.RESPUESTA_GENERICA)]}


DESTINOS = {
    "preventa": "agente_preventa",
    "postventa": "agente_postventa",
    "generica": "respuesta_generica",
}


def elegir_destino(estado: Estado) -> str:
    return DESTINOS[estado["ruta"]]


constructor = StateGraph(Estado)
constructor.add_node("router", router)
constructor.add_node("agente_preventa", agente_preventa)
constructor.add_node("agente_postventa", agente_postventa)
constructor.add_node("respuesta_generica", respuesta_generica)
constructor.add_edge(START, "router")
constructor.add_conditional_edges("router", elegir_destino, list(DESTINOS.values()))
for nodo in DESTINOS.values():
    constructor.add_edge(nodo, END)

graph = constructor.compile(checkpointer=MemorySaver())
