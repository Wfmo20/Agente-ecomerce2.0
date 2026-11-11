"""Registra el webhook del bot: Telegram enviará cada mensaje a PUBLIC_URL/telegram.

    python scripts/set_webhook.py                               # usa PUBLIC_URL del .env
    python scripts/set_webhook.py https://xxxx.trycloudflare.com   # o una URL distinta (ej. túnel)
"""
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

token = os.environ.get("TELEGRAM_TOKEN", "")
secreto = os.environ.get("TELEGRAM_SECRET", "")
base = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PUBLIC_URL", "")).rstrip("/")

if not token or not secreto:
    sys.exit("Faltan TELEGRAM_TOKEN o TELEGRAM_SECRET en .env")
if not base.startswith("https://"):
    sys.exit("PUBLIC_URL debe ser una URL https (Telegram no acepta http).")

r = httpx.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    data={"url": f"{base}/telegram", "secret_token": secreto, "drop_pending_updates": "true"},
    timeout=15,
)
print(f"Webhook → {base}/telegram")
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
