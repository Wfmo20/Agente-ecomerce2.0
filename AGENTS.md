# AGENTS.md · Reglas del proyecto

Proyecto en **Python 3.12** con entorno virtual `.venv`. Configuración en `.env` (copiar desde `.env.example`);
**nunca** poner claves ni valores reales en el código.

## Estructura

```
src/{nombre_agente}/      ← un agente por carpeta
  graph.py                    el grafo (solo nodos, aristas y flujo)
  prompts.py                  un prompt por cada nodo
  tools.py                    las herramientas del agente
api/app.py                ← la API (FastAPI)
main.py                   ← punto de entrada por consola
scripts/                  ← scripts sueltos
tests/                    ← pruebas (pytest)
Procfile · .python-version · requirements.txt   ← despliegue en Heroku
```

## Reglas

1. **Agentes:** cada agente va en `src/{nombre_agente}/` con `graph.py`, `prompts.py` y `tools.py`.
   - Cada nodo tiene **su propio prompt** en `prompts.py`.
   - **Nada de reglas ni prompts dentro de `graph.py`**: el grafo solo arma el flujo e importa los prompts.
2. **Ejecución por consola**, siempre desde la raíz del proyecto:
   - `python main.py {nombre_agente} "mensaje"` → ejecuta el agente con ese mensaje.
   - Flag `--saltos` → además imprime los nodos por los que pasó el grafo.
   - Flag `--diagrama` → imprime el diagrama Mermaid del grafo **sin ejecutarlo**.
3. **API:** va en `api/app.py` (FastAPI) y se levanta con:
   `uvicorn api.app:app --reload --port 8000`
4. **Scripts sueltos** en `scripts/`; **pruebas** en `tests/` y se ejecutan con `pytest`.
5. **Heroku:**
   - `Procfile` con: `web: uvicorn api.app:app --host 0.0.0.0 --port $PORT`
   - `.python-version` con: `3.12`
   - `requirements.txt` **siempre actualizado**: después de instalar algo, ejecutar
     `.venv/bin/python -m pip freeze > requirements.txt` (Windows: `.venv\Scripts\python.exe -m pip freeze > requirements.txt`)
6. **`.gitignore`** con: `.env`, `.venv`, `__pycache__` y `.langgraph_api`.

## Variables de entorno (`.env`)

| Variable | Para qué |
|---|---|
| `GOOGLE_API_KEY` | Clave de Gemini |
| `MODELO` | Modelo a usar (`gemini-3.5-flash-lite`) |
| `TELEGRAM_TOKEN` | Token del bot, lo da BotFather (vacío hasta el paso 5) |
| `TELEGRAM_SECRET` | Secreto que Telegram manda en cada webhook para que la API lo verifique |
| `PUBLIC_URL` | URL https pública (la de Render; vacío hasta desplegar) |
