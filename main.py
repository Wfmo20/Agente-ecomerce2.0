"""Ejecuta un agente por consola, desde la raíz del proyecto.

    python main.py {nombre_agente} "mensaje"
    python main.py {nombre_agente} "mensaje" --saltos     # además, los nodos por los que pasó el grafo
    python main.py {nombre_agente} --diagrama             # diagrama Mermaid, sin ejecutar
"""
import argparse
import importlib
import sys
import uuid


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta un agente de src/{nombre_agente}/.")
    parser.add_argument("agente", help="Nombre del agente (carpeta en src/).")
    parser.add_argument("mensaje", nargs="?", help="Mensaje para el agente.")
    parser.add_argument("--saltos", action="store_true", help="Imprime los nodos por los que pasó el grafo.")
    parser.add_argument("--diagrama", action="store_true", help="Imprime el diagrama Mermaid sin ejecutar.")
    parser.add_argument("--thread", default=None, help="thread_id de la conversación (por defecto, uno nuevo).")
    args = parser.parse_args()

    try:
        modulo = importlib.import_module(f"src.{args.agente}.graph")
    except ModuleNotFoundError:
        sys.exit(f"No existe el agente '{args.agente}' (se busca src/{args.agente}/graph.py).")
    graph = modulo.graph

    if args.diagrama:
        print(graph.get_graph().draw_mermaid())
        return
    if not args.mensaje:
        parser.error("falta el mensaje (o usa --diagrama)")

    config = {"configurable": {"thread_id": args.thread or str(uuid.uuid4())}}
    saltos = []
    for paso in graph.stream({"mensaje": args.mensaje}, config, stream_mode="updates"):
        saltos.extend(paso.keys())
    estado = graph.get_state(config).values

    if args.saltos:
        print(" → ".join(saltos))
        if estado.get("motivo"):
            print(f"motivo: {estado['motivo']}")
        print()
    for clave in ("ruta", "motivo", "respuesta"):
        if clave in estado:
            print(f"{clave}: {estado[clave]}")


if __name__ == "__main__":
    main()
