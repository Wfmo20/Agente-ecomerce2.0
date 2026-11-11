"""Muestra cómo quedó el webhook del bot (getWebhookInfo): URL, mensajes pendientes y último error.

    python scripts/webhook_info.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

token = os.environ.get("TELEGRAM_TOKEN", "")
if not token:
    sys.exit("Falta TELEGRAM_TOKEN en .env")

info = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=15).json()
print(json.dumps(info, indent=2, ensure_ascii=False))

datos = info.get("result", {})
print()
print(f"URL:                 {datos.get('url') or '(sin webhook)'}")
print(f"Updates pendientes:  {datos.get('pending_update_count', 0)}")
if datos.get("last_error_message"):
    fecha = datetime.fromtimestamp(datos["last_error_date"]).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Último error:        {fecha} · {datos['last_error_message']}")
else:
    print("Último error:        ninguno")
