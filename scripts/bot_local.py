"""Bot de Telegram en modo LOCAL (polling): no necesita URL pública, túnel ni servidor desplegado.

    python scripts/bot_local.py                    # se niega si el bot tiene un webhook activo
    python scripts/bot_local.py --quitar-webhook   # borra el webhook (ej. el de Render) y atiende en local

Usa la misma lógica que el webhook (/telegram): autorización por TELEGRAM_ALLOWED_IDS, router y agentes.
Detener: Ctrl+C. Para volver a Render después: python scripts/set_webhook.py
"""
import logging
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import httpx  # noqa: E402

from api.app import atender_telegram, chats_autorizados, log  # noqa: E402  (carga también el .env)
from src.router.graph import graph  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)  # sus logs incluyen la URL con el token
for ruidoso in ("httpx2", "google_genai"):  # llamadas a Gemini: no aportan a la traza
    logging.getLogger(ruidoso).setLevel(logging.WARNING)

token = os.environ.get("TELEGRAM_TOKEN", "")
if not token:
    sys.exit("Falta TELEGRAM_TOKEN en .env")
API = f"https://api.telegram.org/bot{token}"


def llamar(metodo: str, **params) -> dict:
    r = httpx.post(f"{API}/{metodo}", json=params, timeout=params.get("timeout", 0) + 15)
    datos = r.json()
    if not datos.get("ok"):
        sys.exit(f"Telegram respondió error en {metodo}: {datos.get('error_code')} {datos.get('description')}")
    return datos["result"]


bot = llamar("getMe")
webhook = llamar("getWebhookInfo").get("url")
if webhook:
    if "--quitar-webhook" not in sys.argv:
        sys.exit(f"El bot @{bot['username']} tiene un webhook activo ({webhook}).\n"
                 "Mientras exista, Telegram no entrega mensajes por polling. Ejecuta con --quitar-webhook\n"
                 "(después vuelve a dejarlo con: python scripts/set_webhook.py).")
    llamar("deleteWebhook")
    print(f"Webhook {webhook} eliminado.")

autorizados = chats_autorizados()
print(f"Bot @{bot['username']} atendiendo en LOCAL (polling). Chats autorizados: {len(autorizados)}. Ctrl+C para detener.")
if not autorizados:
    print("Aviso: TELEGRAM_ALLOWED_IDS está vacío; todos los chats serán rechazados (el bot les dirá su chat_id).")

desde = 0
try:
    while True:
        try:
            updates = llamar("getUpdates", offset=desde, timeout=30, allowed_updates=["message"])
        except httpx.HTTPError:
            log.error("Sin conexión con Telegram; reintento…")
            continue
        for update in updates:
            desde = update["update_id"] + 1
            atender_telegram(graph, update)
except KeyboardInterrupt:
    print("\nBot detenido.")
