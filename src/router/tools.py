"""Herramientas de los agentes de preventa y postventa.

Leen datos de PRUEBA desde src/router/datos/ (catálogo y pedidos ficticios). Las solicitudes de
devolución, cambio o reclamo se guardan solo en memoria: no envían correos ni tocan sistemas reales.
"""
import json
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from langchain_core.tools import tool

DATOS = Path(__file__).resolve().parent / "datos"
CATALOGO = json.loads((DATOS / "catalogo.json").read_text(encoding="utf-8"))
_PEDIDOS = json.loads((DATOS / "pedidos.json").read_text(encoding="utf-8"))
PLAZO_DEVOLUCION = _PEDIDOS["plazo_devolucion_dias"]
SOLICITUDES: list[dict] = []  # se pierden al reiniciar (son de prueba)


def _norm(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Valparaíso' con 'valparaiso'."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def clp(monto: int) -> str:
    return "$" + f"{monto:,}".replace(",", ".")


def _producto(producto_id: str) -> dict | None:
    return next((p for p in CATALOGO["productos"] if p["id"].upper() == producto_id.strip().upper()), None)


def _pedido(numero: str) -> dict | None:
    numero = numero.strip().lstrip("#")
    return next((p for p in _PEDIDOS["pedidos"] if p["numero"] == numero), None)


# ---------- Preventa ----------

@tool
def buscar_productos(consulta: str) -> list[dict]:
    """Busca productos del catálogo por nombre o categoría (ej. "polera", "zapatillas running", "jeans").
    Devuelve id, nombre, precio en CLP y los colores disponibles. Usa "" para listar todo el catálogo."""
    palabras = [_norm(p).rstrip("s") for p in consulta.split() if len(p) > 2]
    resultado = []
    for p in CATALOGO["productos"]:
        texto = _norm(f"{p['nombre']} {p['categoria']} {' '.join(p['stock'])}")
        if all(w in texto for w in palabras):
            resultado.append({"id": p["id"], "nombre": p["nombre"], "precio": clp(p["precio"]),
                              "colores": list(p["stock"])})
    return resultado


@tool
def consultar_stock(producto_id: str, color: str = "", talla: str = "") -> dict:
    """Stock de un producto (usa el id de buscar_productos, ej. "POL-001"). Opcional: color y talla.
    Devuelve unidades por color y talla; 0 significa agotado."""
    p = _producto(producto_id)
    if p is None:
        return {"error": f"No existe el producto {producto_id}."}
    stock = p["stock"]
    if color:
        clave = next((c for c in stock if _norm(c) == _norm(color)), None)
        if clave is None:
            return {"producto": p["nombre"], "error": f"No viene en color {color}.", "colores": list(stock)}
        stock = {clave: stock[clave]}
    if talla:
        stock = {c: {t: n for t, n in tallas.items() if _norm(t) == _norm(talla)} for c, tallas in stock.items()}
        if not any(stock.values()):
            return {"producto": p["nombre"], "error": f"No existe la talla {talla}.",
                    "tallas": sorted({t for ts in p["stock"].values() for t in ts})}
    return {"producto": p["nombre"], "precio": clp(p["precio"]), "stock_unidades": stock}


@tool
def costo_envio(ciudad: str, total_compra_clp: int = 0) -> dict:
    """Costo y plazo de envío a una ciudad de Chile. Si se conoce el total de la compra en CLP, indica si
    el envío sale gratis."""
    tarifas = CATALOGO["envio"]["tarifas"]
    gratis_desde = CATALOGO["envio"]["gratis_desde"]
    tarifa = tarifas.get(_norm(ciudad))
    if tarifa is None:
        return {"error": f"No hay despacho registrado a {ciudad}.", "ciudades": list(tarifas)}
    gratis = total_compra_clp >= gratis_desde
    return {"ciudad": ciudad, "costo": "$0 (gratis)" if gratis else clp(tarifa["costo"]),
            "costo_normal": clp(tarifa["costo"]), "plazo": tarifa["plazo"],
            "envio_gratis_desde": clp(gratis_desde)}


@tool
def promociones_y_pagos() -> dict:
    """Promociones vigentes (códigos de descuento) y formas de pago aceptadas."""
    return {"promociones": CATALOGO["promociones"], "formas_de_pago": CATALOGO["pagos"]}


# ---------- Postventa ----------

def _ver_pedido(p: dict) -> dict:
    hoy = date.today()
    fecha = hoy - timedelta(days=p["hace_dias"])
    vista = {"numero": p["numero"], "estado": p["estado"], "ciudad": p["ciudad"],
             "items": [{k: (clp(v) if k == "precio" else v) for k, v in i.items()} for i in p["items"]],
             "envio": clp(p["envio"]), "total": clp(p["total"]), "seguimiento": p["seguimiento"]}
    if p["estado"] == "entregado":
        vista["fecha_entrega"] = fecha.isoformat()
        vista["dias_desde_entrega"] = p["hace_dias"]
        vista["dentro_del_plazo_de_devolucion"] = p["hace_dias"] <= PLAZO_DEVOLUCION
    else:
        vista["fecha_compra"] = fecha.isoformat()
        if "entrega_estimada_en_dias" in p:
            vista["entrega_estimada"] = (hoy + timedelta(days=p["entrega_estimada_en_dias"])).isoformat()
    return vista


@tool
def consultar_pedido(numero_pedido: str) -> dict:
    """Estado de un pedido por su número (ej. "4521"): productos, montos, seguimiento y fechas."""
    p = _pedido(numero_pedido)
    if p is None:
        return {"error": f"No encontré el pedido {numero_pedido}. Pide al cliente que revise el número."}
    return _ver_pedido(p)


_VACIAS = {"los", "las", "una", "unos", "unas", "del", "mis", "que", "con", "para"}


def _item_del_pedido(pedido: dict, producto: str) -> list[dict]:
    """Ítems del pedido que calzan con un id ("ZAP-010") o con palabras del nombre ("zapatillas")."""
    por_id = [i for i in pedido["items"] if i["id"].upper() == producto.strip().upper()]
    if por_id:
        return por_id
    palabras = [_norm(w).rstrip("s") for w in producto.replace("(", " ").replace(")", " ").replace(",", " ").split()
                if len(w) > 2 and _norm(w) not in _VACIAS]
    return [i for i in pedido["items"]
            if palabras and all(w in _norm(f"{i['nombre']} {i['color']} {i['talla']}") for w in palabras)]


@tool
def registrar_solicitud(numero_pedido: str, tipo: str, producto: str, motivo: str) -> dict:
    """Registra una solicitud de postventa. tipo: "devolucion", "cambio" o "reclamo" (producto dañado,
    cobro duplicado, etc.). producto: id ("ZAP-010") o nombre del producto del pedido ("zapatillas").
    Llamar SOLO cuando el cliente ya dio número de pedido, producto y motivo. Devuelve el número de caso."""
    tipo = _norm(tipo).replace("ó", "o")
    if tipo not in {"devolucion", "cambio", "reclamo"}:
        return {"error": "tipo debe ser devolucion, cambio o reclamo."}
    p = _pedido(numero_pedido)
    if p is None:
        return {"error": f"No encontré el pedido {numero_pedido}."}
    items = _item_del_pedido(p, producto)
    if len(items) != 1:
        motivo_error = "no está en" if not items else "calza con más de un producto de"
        return {"error": f"'{producto}' {motivo_error} el pedido {p['numero']}. Pregunta al cliente cuál es.",
                "productos_del_pedido": [f"{i['id']} {i['nombre']} ({i['color']}, {i['talla']})" for i in p["items"]]}
    item = items[0]
    if tipo in {"devolucion", "cambio"}:
        if p["estado"] != "entregado":
            return {"error": f"El pedido está {p['estado']}: solo se puede pedir {tipo} cuando ya fue entregado."}
        if p["hace_dias"] > PLAZO_DEVOLUCION:
            return {"error": f"Fuera de plazo: el pedido se entregó hace {p['hace_dias']} días y el plazo es de "
                             f"{PLAZO_DEVOLUCION} días. Puede registrar un reclamo si el producto tiene una falla."}
    caso = {"caso": f"SOL-{len(SOLICITUDES) + 1:04d}", "tipo": tipo, "pedido": p["numero"],
            "producto": item["nombre"], "motivo": motivo, "estado": "registrada",
            "siguiente_paso": "Un ejecutivo contactará al cliente en un máximo de 2 días hábiles con las instrucciones."}
    SOLICITUDES.append(caso)
    return caso


TOOLS_PREVENTA = [buscar_productos, consultar_stock, costo_envio, promociones_y_pagos]
TOOLS_POSTVENTA = [consultar_pedido, registrar_solicitud]
TOOLS = TOOLS_PREVENTA + TOOLS_POSTVENTA
