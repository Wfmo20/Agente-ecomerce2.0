# Evidencias

Todas las pruebas son **LOCALES** salvo que se indique lo contrario. Claves, tokens y secretos se muestran como
`<API_KEY>` o se taparon en las capturas. Los datos de la tienda (catálogo, pedidos) son de **prueba**.

Archivos:
- `01_api_local_acceso.txt`: peticiones a la API local y sus respuestas (acceso permitido y rechazado).
- `02_log_servidor_local.txt`: log del servidor local de esas mismas peticiones (ruta, motivo y herramientas).
- `03_telegram_*.png`: capturas del chat con el bot ejecutado en local (`scripts/bot_local.py`) y de su terminal.
- `04_pytest.txt`: salida de `pytest -v`.

## API FastAPI (`/chat`)

| # | Entorno y fecha | Solicitud | Resultado esperado | Resultado obtenido | Observaciones |
|---|---|---|---|---|---|
| A1 | LOCAL · 2026-11-11 | `/chat` **sin** `X-API-Key` | 401, sin llamar al modelo | 401 `Falta X-API-Key o no es válida.`; log: `Acceso rechazado a /chat (X-API-Key ausente)` | Acceso rechazado (01, §2) |
| A2 | LOCAL · 2026-11-11 | `/chat` con clave **incorrecta** | 401 | 401; log: `X-API-Key incorrecta` | Acceso rechazado (01, §3) |
| A3 | LOCAL · 2026-11-11 | "¿tienen la polera básica azul en talla M?" con clave correcta | preventa; azul M agotada (stock 0); ofrece tallas/colores con stock | preventa; `consultar_stock`; "azul M agotada… stock en S (4), L (6) y XL (2)" | Acceso permitido. Cifras iguales a `catalogo.json` (01, §4) |
| A4 | LOCAL · 2026-11-11 | "¿cuánto cuesta el envío a Valparaíso?" | $4.990, 2 a 3 días hábiles, gratis desde $49.990 | Igual; `costo_envio(ciudad='Valparaíso')` | Conserva cifras y unidades (§5) |
| A5 | LOCAL · 2026-11-11 | "mi pedido 4521 llegó roto" → "las zapatillas" (mismo `user_id`) | Consulta el pedido, pregunta cuál producto (hay dos) y luego registra el reclamo | `consultar_pedido('4521')` → pregunta → `registrar_solicitud(reclamo, 'zapatillas')` → caso `SOL-0001` | Memoria por `user_id`; solicita el dato faltante antes de concluir (§6–7) |
| A5b | LOCAL · 2026-11-11 | "quiero devolver las zapatillas del pedido 4498" | Rechaza: fuera del plazo de 30 días | "ya pasaron 45 días… fuera del plazo" | Límite del agente informado, no se registra nada (§8) |
| A6 | LOCAL · 2026-11-11 | "¿qué hora es en Tokio?" | generica, sin modelo en la respuesta | generica | — |
| A7 | LOCAL · 2026-11-11 | `texto` vacío | 422 | 422 | Entrada inválida |
| A8 | LOCAL · 2026-11-11 | `/telegram` sin secreto | 403 | 403; log: `Webhook /telegram rechazado` | — |

## Telegram (canal elegido)

| # | Entorno y fecha | Solicitud | Resultado esperado | Resultado obtenido | Observaciones |
|---|---|---|---|---|---|
| T1 | LOCAL · 2026-11-11 15:54 | "hola" desde un chat **no autorizado** (`TELEGRAM_ALLOWED_IDS` vacío) | "No estás autorizado… tu chat_id es …"; no llama al modelo | Respuesta de rechazo; log `WARNING Telegram chat_id=… rechazado` | Acceso rechazado. `03a_terminal_rechazado.txt` + captura `03_telegram_rechazado.png`. Luego se agregó el chat_id a `TELEGRAM_ALLOWED_IDS` |
| T2 | LOCAL · 2026-11-11 16:44 | "¿tienen la polera básica azul en talla M?" (chat autorizado) | preventa; agotada y alternativas con precio | ruta=preventa; `buscar_productos('polera')`, `consultar_stock(POL-001, azul)`, `consultar_stock(POL-002, azul)` | Acceso permitido. `03b_terminal_autorizado.txt` + captura del chat |
| T3 | LOCAL · 2026-11-11 16:45 | "¿cuánto cuesta el envío a Valparaíso?" | $4.990, 2 a 3 días hábiles | ruta=preventa; `costo_envio(ciudad='Valparaíso')` | Captura del chat |
| T4 | LOCAL · 2026-11-11 16:45 | "mi pedido 4521 llegó roto" → "las zapatillas" | Pregunta el producto, luego caso `SOL-…` | ruta=postventa; `consultar_pedido('4521')` → `registrar_solicitud(producto='Zapatillas running Ligera', tipo='reclamo')` | Pide el dato faltante antes de registrar |
| T5 | LOCAL · 2026-11-11 16:46 | "quiero devolver las zapatillas del pedido 4498" | Fuera de plazo (45 días > 30) | ruta=postventa; `consultar_pedido('4498')`, sin registrar solicitud | Límite informado |
| T6 | LOCAL · 2026-11-11 16:46 | "¿qué hora es en Tokio?" | generica | ruta=generica | — |
| T7 | LOCAL · 2026-11-11 16:37–16:38 | Mensajes libres ("adidas", "zapatillas", el nombre del usuario) | Preventa busca en el catálogo; lo ajeno va a generica | preventa con `buscar_productos('adidas')` y `('zapatillas')`; el nombre → generica | Observación: no hay marca "adidas" en el catálogo de prueba |

## Despliegue en Render (opcional, +1)

| # | Entorno y fecha | Solicitud | Resultado esperado | Resultado obtenido | Observaciones |
|---|---|---|---|---|---|
| R1 | RENDER · 2026-11-11 | `GET /health` | 200 | 200 `{"ok":true,"modelo":"gemini-3.5-flash-lite"}` | https://agente-ecomerce2-0.onrender.com |
| R2 | RENDER · 2026-11-11 | `setWebhook` + `getWebhookInfo` | Webhook en `…/telegram`, sin errores | "Webhook was set", 0 pendientes, sin errores | Versión anterior (agentes cascarón) |
| R3 | RENDER · _fecha_ | Mensajes al bot desplegado | Igual que T1–T5, visibles en **Logs** de Render | _pendiente_ | Tras desplegar esta versión |
