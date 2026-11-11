# Ecommerce Router · agente + API

Chat de una tienda online. Cada mensaje del cliente pasa por un **router** (LangGraph + Gemini con salida
estructurada) que decide a qué agente va y por qué:

| Ruta | Cuándo | Nodo |
|---|---|---|
| `preventa` | Quiere comprar o pregunta por productos, precios, tallas, stock, promociones, envío o formas de pago. | `agente_preventa` |
| `postventa` | Ya compró: reclamo, seguimiento de un pedido, devolución, cambio, garantía o producto dañado. | `agente_postventa` |
| `generica` | No tiene que ver con la tienda (clima, chistes, hora…) o es un saludo sin pedido. | `respuesta_generica` |

Por ahora los agentes destino son cascarones: solo importa que el router enrute bien. Se expone como API (FastAPI) y como bot de Telegram.
Reglas del proyecto en [AGENTS.md](AGENTS.md).

```
src/router/        graph.py · prompts.py · tools.py     ← el agente
api/app.py         API FastAPI (/health, /chat, /telegram)
main.py            ejecutar agentes por consola
scripts/           probar_router.py · test_router.py · set_webhook.py · webhook_info.py
tests/             test_router.py (15 casos) · test_api.py (API y Telegram, sin modelo)
bruno/             colección de requests (local ↔ Render)
Procfile · .python-version · requirements.txt        ← despliegue (Render)
```

## 1. Preparar

Requisitos: Python 3.12 y una clave de Gemini (<https://aistudio.google.com/apikey>).

```bash
python3.12 -m venv .venv                 # Windows: py -3.12 -m venv .venv
source .venv/bin/activate                # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                     # Windows: copy .env.example .env
```

Completa `.env` (nunca lo subas al repositorio). El proyecto lee **solo** el `.env` de su raíz.

| Variable | Para qué | Cuándo |
|---|---|---|
| `GOOGLE_API_KEY` | Clave de Gemini (la lee `langchain-google-genai`) | Desde el inicio |
| `MODELO` | Modelo del router (`gemini-3.5-flash-lite`) | Desde el inicio |
| `TELEGRAM_TOKEN` | Token del bot, lo entrega BotFather | Paso 6 |
| `TELEGRAM_SECRET` | Secreto que Telegram envía en cada webhook para que la API lo verifique | Paso 6 |
| `PUBLIC_URL` | URL https pública de la app (la de Render) | Después de desplegar |

## 2. Correr el router por consola

```bash
python main.py router "mi pedido 4521 llegó roto"              # ruta, motivo y respuesta
python main.py router "mi pedido 4521 llegó roto" --saltos     # además: router → <nodo> y el motivo
python main.py router --diagrama                               # diagrama Mermaid, sin ejecutar
```

## 3. Levantar la API

```bash
uvicorn api.app:app --reload --port 8000
```

- Swagger: <http://localhost:8000/docs> → abre un endpoint → **Try it out** (ya trae un ejemplo) → **Execute**.
- Salud: <http://localhost:8000/health>
- Para detenerla: `Ctrl+C`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | `{"ok": true, "modelo": "..."}` |
| POST | `/chat` | Recibe `{"user_id", "texto"}` y devuelve `{"ruta", "motivo", "respuesta"}`. Memoria por `user_id`. |
| POST | `/telegram` | Webhook de Telegram (no aparece en el Swagger). Ver sección 6. |

Errores de `/chat`: **422** si falta `user_id` o `texto` (o vienen vacíos) · **502** si el modelo falla
(el detalle queda en el log del servidor, nunca en la respuesta).

Ejemplo con curl (macOS / Linux / Git Bash):

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "cliente-123", "texto": "¿tienen la polera azul en talla M?"}'
```

En PowerShell (Windows):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat -ContentType "application/json; charset=utf-8" `
  -Body '{"user_id": "cliente-123", "texto": "¿tienen la polera azul en talla M?"}'
```

**Bruno (opcional):** Open Collection → carpeta `bruno/` → entorno `local` o `render` (arriba a la derecha).
En `bruno/environments/render.bru` cambia `baseUrl` por la URL de tu app.

## 4. Correr las pruebas

```bash
pytest -v                           # test_api.py (sin modelo) + 15 casos del router; exige al menos 13 aciertos (fallos sueltos salen como XFAIL)
python scripts/test_router.py       # tabla: mensaje, esperado, obtenido, ✔/✘ y motivo
python scripts/probar_router.py     # los 6 mensajes de ejemplo con su ruta
```

`tests/test_api.py` no usa el modelo ni Telegram. Las pruebas del router se saltan si no hay `GOOGLE_API_KEY` en `.env`.

## 5. Desplegar en Render

Se usa [Render](https://render.com) (plan **Free**, no pide tarjeta) en vez de Heroku, que ya no tiene plan gratis.
Render despliega desde GitHub: primero sube el proyecto a tu repositorio (`git push origin main`).
Instala `requirements.txt` con Python `3.12` (lo lee de `.python-version`).

1. Entra a Render con **Sign in with GitHub** → **+ New** → **Web Service** → elige el repositorio
   (si no aparece: **Configure account** y dale acceso a ese repositorio).
2. Configura:

   | Campo | Valor |
   |---|---|
   | Language | `Python 3` |
   | Branch | `main` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn api.app:app --host 0.0.0.0 --port $PORT` (el mismo del `Procfile`) |
   | Instance Type | **Free** |

3. En **Environment Variables** agrega `GOOGLE_API_KEY`, `MODELO`, `TELEGRAM_TOKEN` y `TELEGRAM_SECRET`
   (el nombre en **KEY**, el valor en **VALUE**; los mismos de tu `.env`) → **Deploy Web Service**.
4. Cuando diga **Live**, copia la URL (`https://NOMBRE-xxxx.onrender.com`, debajo del nombre del servicio)
   y ponla como `PUBLIC_URL` en tu `.env` local (la usa `set_webhook.py`).

Prueba: `https://NOMBRE-xxxx.onrender.com/health` y `/docs`. En Bruno, entorno `render`
(antes cambia `baseUrl` en `bruno/environments/render.bru`).
Cada `git push` a `main` vuelve a desplegar solo; los errores se ven en la pestaña **Logs** del servicio.
Después de instalar un paquete nuevo: `pip freeze > requirements.txt` y vuelve a hacer push.

> En el plan Free la app **se duerme tras ~15 min sin uso**: el primer mensaje puede tardar ~50 s en responder
> (Telegram reintenta solo). La memoria de las conversaciones (`MemorySaver`) vive en la RAM: se borra cuando la
> app se duerme o se vuelve a desplegar.

## 6. Telegram

El bot usa solo `httpx` (sin librerías de bot). Cómo funciona `POST /telegram`:
- Verifica que la cabecera `X-Telegram-Bot-Api-Secret-Token` sea igual a `TELEGRAM_SECRET`; si no, **403**.
- Lee `message.chat.id` y `message.text`; los updates sin texto (stickers, fotos…) se ignoran.
- Pasa el texto por el router con `thread_id = chat_id` (memoria por chat) y contesta con `sendMessage`.
- Siempre responde **200** a Telegram (aunque el modelo falle: en ese caso le avisa al usuario), para que no reintente.
- En el log queda `Telegram chat_id=… → ruta=… · motivo: …` por cada mensaje.

### 6.1 Crear el bot

1. En Telegram, habla con **@BotFather** → `/newbot` → elige nombre y usuario (debe terminar en `bot`) → copia el **token**.
2. En `.env`: `TELEGRAM_TOKEN=<token>` y `TELEGRAM_SECRET=<una frase larga solo con letras, números, - o _>`.

### 6.2 Conectar en Render (en orden)

1. Variables en Render: servicio → **Environment** → `TELEGRAM_TOKEN` y `TELEGRAM_SECRET` (iguales a tu `.env`)
   → **Save, rebuild, and deploy**.
2. Commit y push a GitHub (Render redespliega solo):
   ```bash
   git add .
   git commit -m "telegram: webhook con secreto y sendMessage"
   git push origin main
   ```
3. Registrar el webhook (con `PUBLIC_URL` de Render en tu `.env`) y confirmar:
   ```bash
   python scripts/set_webhook.py        # debe imprimir "ok": true, "Webhook was set"
   python scripts/webhook_info.py       # URL .../telegram, 0 pendientes y "Último error: ninguno"
   ```
4. Escribirle al bot los 6 mensajes y revisar en la pestaña **Logs** de Render que cada uno tomó la ruta correcta:

   | Mensaje | Ruta esperada |
   |---|---|
   | ¿tienen la polera azul en talla M? | preventa |
   | mi pedido 4521 llegó roto | postventa |
   | hola | generica |
   | ¿cuánto cuesta el envío a Valparaíso? | preventa |
   | quiero devolver unas zapatillas | postventa |
   | ¿qué hora es en Tokio? | generica |

5. **Si no responde**, revisar:
   - `python scripts/webhook_info.py`: la URL debe ser **https** y terminar en **`/telegram`**; mira `Último error`
     (`403 Forbidden` = secreto distinto; `404` = falta `/telegram`; `502`/timeout = la app no levanta o estaba dormida: ver logs).
   - El **secreto es igual** en ambos lados: **Environment** de Render vs `.env`. Si cambias el
     secreto, vuelve a ejecutar `set_webhook.py`.
   - El **token es correcto** (en **Environment** de Render y en `.env`): si `set_webhook.py` responde
     `401 Unauthorized`, el token está mal. En los logs, `No se pudo enviar el mensaje a Telegram` también apunta al token.
   - **Logs** de Render: si aparece `Falló el grafo router`, el problema es `GOOGLE_API_KEY` o `MODELO`.

### 6.3 Opcional: probar en local antes de desplegar

Telegram necesita una URL https pública; un túnel rápido de Cloudflare la da sin cuenta
(requiere [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)):

```bash
uvicorn api.app:app --reload --port 8000                  # terminal 1
cloudflared tunnel --url http://localhost:8000            # terminal 2: copia la URL https://xxxx.trycloudflare.com
python scripts/set_webhook.py https://xxxx.trycloudflare.com   # terminal 3 (o ponla como PUBLIC_URL en .env)
python scripts/webhook_info.py
```

Escríbele al bot: las rutas aparecen en la terminal 1. La URL del túnel cambia cada vez que lo abres; al
terminar, `Ctrl+C` en las dos terminales y vuelve a ejecutar `set_webhook.py` con la URL de Render.
