"""Pruebas de las herramientas (sin modelo): cifras exactas, plazos y validaciones."""
from src.router import tools


def test_stock_agotado_y_disponible():
    r = tools.consultar_stock.invoke({"producto_id": "POL-001", "color": "azul", "talla": "M"})
    assert r["stock_unidades"] == {"azul": {"M": 0}} and r["precio"] == "$12.990"
    r = tools.consultar_stock.invoke({"producto_id": "POL-002", "color": "Azul", "talla": "m"})
    assert r["stock_unidades"] == {"azul": {"M": 9}}


def test_producto_inexistente():
    assert "error" in tools.consultar_stock.invoke({"producto_id": "XXX-1"})


def test_buscar_sin_tildes_ni_plural():
    ids = [p["id"] for p in tools.buscar_productos.invoke({"consulta": "Zapatillas"})]
    assert ids == ["ZAP-010", "ZAP-011"]


def test_envio_valparaiso_con_y_sin_tilde():
    for ciudad in ("Valparaíso", "valparaiso"):
        r = tools.costo_envio.invoke({"ciudad": ciudad})
        assert r["costo"] == "$4.990" and r["plazo"] == "2 a 3 días hábiles"


def test_envio_gratis_desde_49990():
    assert tools.costo_envio.invoke({"ciudad": "Santiago", "total_compra_clp": 49990})["costo"] == "$0 (gratis)"
    assert tools.costo_envio.invoke({"ciudad": "Santiago", "total_compra_clp": 49989})["costo"] == "$3.990"


def test_ciudad_sin_despacho():
    assert "error" in tools.costo_envio.invoke({"ciudad": "Isla de Pascua"})


def test_pedido_y_montos():
    r = tools.consultar_pedido.invoke({"numero_pedido": "#4521"})
    assert r["estado"] == "entregado" and r["total"] == "$67.980" and r["dentro_del_plazo_de_devolucion"]
    assert "error" in tools.consultar_pedido.invoke({"numero_pedido": "1"})


def test_devolucion_fuera_de_plazo_y_no_entregado():
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4498", "tipo": "devolución", "producto": "ZAP-011", "motivo": "x"})
    assert "Fuera de plazo" in r["error"]
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4530", "tipo": "cambio", "producto": "JEA-020", "motivo": "x"})
    assert "en camino" in r["error"]


def test_reclamo_registra_caso():
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4521", "tipo": "reclamo", "producto": "ZAP-010", "motivo": "llegó roto"})
    assert r["caso"].startswith("SOL-") and r["producto"] == "Zapatillas running Ligera"


def test_producto_que_no_esta_en_el_pedido():
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4521", "tipo": "reclamo", "producto": "JEA-020", "motivo": "x"})
    assert "no está en el pedido" in r["error"]


def test_producto_por_nombre():
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4521", "tipo": "reclamo", "producto": "las zapatillas", "motivo": "x"})
    assert r["producto"] == "Zapatillas running Ligera"
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4521", "tipo": "reclamo", "producto": "Zapatillas running Ligera (negro, 41)", "motivo": "x"})
    assert r["producto"] == "Zapatillas running Ligera"
    r = tools.registrar_solicitud.invoke({"numero_pedido": "4521", "tipo": "cambio", "producto": "los la polera", "motivo": "x"})
    assert r["producto"] == "Polera básica algodón"
