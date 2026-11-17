# Canal Telegram con voz (n8n en la nube)

Flujo `telegram_voz.json`: un **segundo bot** de Telegram atendido por n8n. Acepta **texto y notas de voz**: la voz
se transcribe con Gemini y el texto va a la misma API (`/chat` en Render, con `X-API-Key`), así que responden los
mismos agentes, herramientas y Postgres.

```
Telegram Trigger ─► Autorizar y clasificar ─► Según el tipo ─┬─ texto ─► Texto escrito ──────────────────────────┐
                                                             ├─ voz ───► Descargar audio ─► Audio a base64 ─►     │
                                                             │           Transcribir con Gemini ─► Texto de la voz ┤
                                                             └─ no_autorizado ─► Responder no autorizado          │
                     Mensaje para el agente ◄─────────────────────────────────────────────────────────────────────┘
                       └─► Llamar al agente (/chat) ─┬─► Responder            ("🎤 Entendí: «…»" + respuesta)
                                                     └─► Responder error     (API caída, texto vacío o muy largo)
```

**Por qué un segundo bot:** Telegram entrega los mensajes de un bot a un solo webhook. @wfmo20_bot sigue en Render;
si n8n usara ese mismo bot, Render dejaría de recibir mensajes.

## Pasos (una vez)

1. **Bot nuevo:** en Telegram, @BotFather → `/newbot` → copia el token.
2. **Cuenta n8n:** <https://n8n.io> → *Get started* (prueba gratis en la nube).
3. **Importar:** *Create workflow* → menú `⋯` (arriba a la derecha) → **Import from File** → `n8n/telegram_voz.json`.
4. **Credenciales** (en cada nodo marcado en rojo → *Credential* → *Create new credential*):

   | Nodo(s) | Tipo de credencial | Valor |
   |---|---|---|
   | Telegram Trigger, Descargar audio, Responder… (los 4 de Telegram) | **Telegram API** | Token del bot nuevo (crearla una vez y elegirla en los demás) |
   | Transcribir con Gemini | **Header Auth** | Name `x-goog-api-key` · Value: tu `GOOGLE_API_KEY` |
   | Llamar al agente (/chat) | **Header Auth** | Name `X-API-Key` · Value: la `API_KEY` de Render |

5. **Autorizados:** nodo **Autorizar y clasificar** → reemplaza `PEGA_AQUI_TU_CHAT_ID` por tu chat_id
   (varios: `['111', '222']`). Si no lo sabes, escríbele al bot ya activo: te responde "Tu chat_id es …".
6. **Save** → interruptor **Active** (arriba). n8n registra solo el webhook del bot nuevo.

## Probar

| Mensaje al bot nuevo | Qué debe pasar |
|---|---|
| Texto: `¿cuánto cuesta el envío a Valparaíso?` | Respuesta de preventa: $4.990, 2 a 3 días hábiles |
| **Nota de voz:** "¿tienen la polera básica azul en talla M?" | `🎤 Entendí: «…»` + la respuesta (agotada y alternativas) |
| Voz: "mi pedido 4521 llegó roto" → voz: "las zapatillas" | Pregunta el producto y luego entrega `SOL-…` (memoria por chat) |
| Desde un chat no autorizado | "No estás autorizado… Tu chat_id es …", sin llamar a la API |

Cada ejecución queda en n8n → **Executions** (se ve el texto transcrito y la respuesta de `/chat`): sirve de
evidencia. La primera respuesta puede tardar ~50 s si Render estaba dormido (el nodo espera hasta 90 s).

## Seguridad

- Las claves quedan en las credenciales de n8n (cifradas), no en el flujo exportado.
- Doble control: lista de chat_id en n8n y `X-API-Key` en la API.
- Conversaciones separadas: el flujo usa `user_id = n8n-<chat_id>` (en la API, `thread_id = api-n8n-<chat_id>`).
- Para detener: interruptor **Active** apagado.
