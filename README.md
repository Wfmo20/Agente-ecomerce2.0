# Tienda online · agentes de preventa y postventa en Telegram

Taller de implementación (Agentic AI · Curso 2). Chat de atención de una tienda online de ropa y zapatillas:
el cliente escribe por **Telegram** (o por la **API FastAPI**), un **router** (LangGraph + Gemini) decide qué
agente lo atiende y ese agente responde con **herramientas sobre un catálogo y pedidos de prueba**.

| Ruta | Cuándo | Qué hace |
|---|---|---|
| `preventa` | Quiere comprar: productos, precios, tallas, stock, envío, promociones, pagos. | Agente con herramientas `buscar_productos`, `consultar_stock`, `costo_envio`, `promociones_y_pagos`. |
| `postventa` | Ya compró: seguimiento, devolución, cambio, reclamo, producto dañado. | Agente con `consultar_pedido` y `registrar_solicitud` (plazo de devolución de 30 días). |
| `generica` | Saludos o temas ajenos a la tienda (clima, hora, chistes). | Respuesta fija, sin usar el modelo. |

## Integrantes y aportes

| Nombre y apellidos | Aporte |
|---|---|
| _(completar)_ | _(completar)_ |
| _(completar)_ | _(completar)_ |

## Opción elegida

**Opción 2 · Un canal de atención: Telegram**, más la API FastAPI con acceso protegido (`/chat`) que usa el mismo
grafo.

- **Problema que resuelve:** responder 24/7 las consultas típicas de una tienda (stock, envío, estado de pedidos,
  devoluciones) con datos de la tienda, sin inventarlos, y derivar cada mensaje al agente correcto.
- **Qué reutiliza del trabajo anterior:** el router de ecommerce (LangGraph, salida estructurada `Decision`,
  memoria por hilo con `MemorySaver`), sus 15 casos de prueba y la API FastAPI con `/health`, `/chat` y `/telegram`.
  **Nuevo en este taller:** los agentes de preventa y postventa con herramientas y datos de prueba, el control de
  acceso (API key y lista de chats autorizados), el bot en modo local (`scripts/bot_local.py`), el manejo de
  entradas inválidas y las evidencias.

```
Telegram ──► /telegram (webhook, Render)  ─┐
         └─► scripts/bot_local.py (LOCAL) ─┼─► autorización ─► router ─┬─► agente_preventa  ─► tools ─► catalogo.json
curl/Swagger ─► /chat (X-API-Key) ─────────┘                          ├─► agente_postventa ─► tools ─► pedidos.json
                                                                      └─► respuesta_generica
```

```
src/router/        graph.py · prompts.py · tools.py · datos/ (catálogo y pedidos de PRUEBA)
api/app.py         API FastAPI (/health, /chat, /telegram) + atención de Telegram
main.py            ejecutar el agente por consola
scripts/           bot_local.py · set_webhook.py · webhook_info.py · probar_router.py · test_router.py
tests/             test_api.py · test_tools.py (sin modelo) · test_router.py · test_agentes.py (con modelo)
evidencias/        EVIDENCIAS.md + registros y capturas de la ejecución local
bruno/             colección de requests (local ↔ Render)
Procfile · .python-version · requirements.txt        ← despliegue
```

## 1. Qué se prepara a mano

Necesita **internet**: Gemini (Google) y Telegram son servicios externos. No hay pagos: Gemini tiene capa
gratuita y el bot de Telegram es gratis.

1. **Clave de Gemini:** <https://aistudio.google.com/apikey> → *Create API key*. Va en `GOOGLE_API_KEY`.
2. **Bot de Telegram (prueba):** en Telegram, **@BotFather** → `/newbot` → nombre y usuario (termina en `bot`) →
   copia el token a `TELEGRAM_TOKEN`. Usa un bot propio de prueba, no uno de producción.
3. **Tu `chat_id`:** inicia el bot (paso 4) y escríbele: si no estás autorizado te responde
   *"No estás autorizado… Tu chat_id es 123456789"*. Ponlo en `TELEGRAM_ALLOWED_IDS` (varios, separados por coma)
   y reinicia el bot.
4. **`API_KEY`** (para `/chat`) y **`TELEGRAM_SECRET`** (solo webhook): invéntalos, largos y al azar, por ejemplo:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## 2. Instalar

Requisitos: Python 3.12.

```bash
python3.12 -m venv .venv                 # Windows: py -3.12 -m venv .venv
source .venv/bin/activate                # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                     # Windows: copy .env.example .env
```

Completa `.env` (nunca lo subas al repositorio; el proyecto lee **solo** el `.env` de su carpeta raíz):

| Variable | Para qué | Obligatoria |
|---|---|---|
| `GOOGLE_API_KEY` | Clave de Gemini | Sí |
| `MODELO` | Modelo (`gemini-3.5-flash-lite`) | Sí |
| `API_KEY` | Clave que se envía en la cabecera `X-API-Key` a `/chat`. Vacía = `/chat` responde 503 a todos | Para la API |
| `TELEGRAM_TOKEN` | Token del bot (BotFather) | Para Telegram |
| `TELEGRAM_ALLOWED_IDS` | `chat_id` autorizados, separados por coma. Vacío = nadie autorizado | Para Telegram |
| `TELEGRAM_SECRET` | Secreto del webhook (solo en el despliegue) | Webhook |
| `PUBLIC_URL` | URL https pública (solo en el despliegue) | Webhook |

## 3. Iniciar, probar y detener (LOCAL)

### 3.1 Bot de Telegram en local (canal elegido)

```bash
python scripts/bot_local.py                    # Ctrl+C para detener
```

Usa *polling*: no necesita URL pública ni túnel. Si el bot tiene un webhook activo (por ejemplo el de Render),
el script se detiene y explica; para atender en local igual: `python scripts/bot_local.py --quitar-webhook`
(después, para volver a Render: `python scripts/set_webhook.py`). En la terminal queda el registro de cada mensaje:

```
INFO agente_postventa → consultar_pedido(numero_pedido='4521')
INFO Telegram chat_id=123456789 → ruta=postventa · motivo: El cliente reporta un producto dañado…
WARNING Telegram chat_id=987654321 rechazado (no está en TELEGRAM_ALLOWED_IDS)
```

Mensajes de prueba sugeridos (en este orden, en el mismo chat):

| Mensaje | Qué debe pasar |
|---|---|
| ¿tienen la polera básica azul en talla M? | preventa: está agotada (stock 0) y ofrece alternativas con stock, con precio exacto |
| ¿cuánto cuesta el envío a Valparaíso? | preventa: **$4.990**, **2 a 3 días hábiles**, gratis desde **$49.990** |
| mi pedido 4521 llegó roto | postventa: consulta el pedido y **pregunta cuál producto** (tiene dos) |
| las zapatillas | postventa: registra el reclamo y entrega el número de caso `SOL-…` |
| quiero devolver las zapatillas del pedido 4498 | postventa: rechaza, fuera del plazo de 30 días |
| ¿qué hora es en Tokio? | generica: este chat es para la tienda |

Datos de prueba: pedidos **4521** (entregado hace 3 días, 2 productos), **4530** (en camino), **4540** (en
preparación) y **4498** (entregado hace 45 días). Catálogo completo en `src/router/datos/catalogo.json`.

### 3.2 API FastAPI

```bash
uvicorn api.app:app --reload --port 8000       # Ctrl+C para detener
```

- Swagger: <http://localhost:8000/docs> → **Authorize** (pega tu `API_KEY`) → `/chat` → **Try it out** → **Execute**.
- Salud: <http://localhost:8000/health>

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" -H "X-API-Key: TU_API_KEY" \
  -d '{"user_id": "cliente-123", "texto": "¿tienen la polera azul en talla M?"}'
```

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat -ContentType "application/json; charset=utf-8" `
  -Headers @{ "X-API-Key" = "TU_API_KEY" } -Body '{"user_id": "cliente-123", "texto": "¿tienen la polera azul en talla M?"}'
```

Respuesta: `{"ruta", "motivo", "respuesta", "herramientas"}` (`herramientas` = qué consultó el agente).

| Código | Cuándo |
|---|---|
| 200 | Respuesta del agente |
| 401 | Falta `X-API-Key` o no coincide con `API_KEY` |
| 422 | Falta `user_id`/`texto`, vienen vacíos o el texto supera 1000 caracteres |
| 502 | El modelo falló o no respondió (el detalle queda solo en el log del servidor) |
| 503 | El servidor no tiene `API_KEY` configurada |

### 3.3 Consola y pruebas

```bash
python main.py router "mi pedido 4530" --saltos      # ruta, motivo, herramientas usadas y respuesta
python main.py router --diagrama                     # diagrama Mermaid del grafo

pytest -v                         # todo: API, herramientas, router (≥13/15) y agentes con el modelo
pytest tests/test_api.py tests/test_tools.py -v      # solo lo que no usa el modelo (sin clave ni internet)
python scripts/test_router.py     # tabla de los 15 casos del router: esperado vs obtenido
```

Las pruebas con el modelo se saltan si no hay `GOOGLE_API_KEY`.

## 4. Seguridad y efectos reales

- **Acceso:** `/chat` exige `X-API-Key` (comparación en tiempo constante); sin `API_KEY` en el servidor nadie
  entra. En Telegram solo responden los chats de `TELEGRAM_ALLOWED_IDS`; los demás reciben "no autorizado" y no
  se llama al modelo. El webhook `/telegram` rechaza con 403 lo que no trae `TELEGRAM_SECRET`.
- **Secretos:** solo en `.env` (ignorado por git) o en las variables del servicio. Los logs no muestran claves
  ni el token (se silencia el log de `httpx`, que incluye la URL con el token). Errores del modelo: el cliente
  recibe un mensaje claro, sin stack trace.
- **Sin efectos reales:** el catálogo y los pedidos son ficticios; `registrar_solicitud` solo guarda en memoria
  (no envía correos ni toca sistemas). El bot solo responde a quien le escribe.
- **Costos:** mensajes de máximo 1000 caracteres, historial acotado a 12 mensajes, 1 reintento y 60 s de
  timeout por llamada al modelo. Para detener todo: `Ctrl+C` en cada terminal (y en Render, **Suspend**).

## 5. Límites conocidos

- La memoria de las conversaciones y las solicitudes registradas viven en RAM: se borran al reiniciar.
- Datos de prueba fijos (8 productos, 4 pedidos, 8 ciudades); no hay compra ni pago real.
- No se verifica que quien consulta un pedido sea su dueño (en un sistema real se pediría correo o RUT).
- El modelo no es determinista: el router acierta ≥13/15 casos en las pruebas (15/15 en nuestra ejecución) y las
  respuestas pueden variar en redacción; las cifras salen de las herramientas.
- `gemini-3.5-flash-lite` ignora `temperature` (usa valores fijos de muestreo).
- Telegram: solo mensajes de texto (fotos, audios y stickers se ignoran).

## 6. Despliegue en Render (opcional, +1)

Desplegado en **Render** (plan Free) desde este repositorio: <https://agente-ecomerce2-0.onrender.com/health>.

1. Render → **+ New → Web Service** → el repositorio → Build `pip install -r requirements.txt` →
   Start `uvicorn api.app:app --host 0.0.0.0 --port $PORT` (el mismo del `Procfile`) → Instance **Free**.
2. **Environment:** `GOOGLE_API_KEY`, `MODELO`, `API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_SECRET`,
   `TELEGRAM_ALLOWED_IDS` → **Deploy**.
3. Con la URL pública en `PUBLIC_URL` del `.env` local:
   ```bash
   python scripts/set_webhook.py      # "Webhook was set"
   python scripts/webhook_info.py     # URL …/telegram, 0 pendientes, sin errores
   ```
4. Cada `git push` a `main` redespliega. Errores en la pestaña **Logs**.

En el plan Free la app se duerme tras ~15 min sin uso: el primer mensaje puede tardar ~50 s.
**Si no responde:** `webhook_info.py` muestra el último error (`403` = secreto distinto, `404` = falta
`/telegram`); revisa que el token y el secreto sean iguales en Render y en `.env`, y los **Logs**
(`Falló el grafo router` = problema con `GOOGLE_API_KEY` o `MODELO`).

**Para otra plataforma (Heroku, etc.):** arranque `uvicorn api.app:app --host 0.0.0.0 --port $PORT`; puerto,
URL y secretos se configuran por variables de entorno; no hay datos que conservar (todo es de prueba y en
memoria); servicios externos: Gemini y Telegram.

Bruno (opcional): Open Collection → carpeta `bruno/` → entorno `local` o `render` → en el entorno completa la
variable secreta `apiKey` con tu `API_KEY` (Bruno no la guarda en los archivos).
