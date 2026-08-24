"""CLI interativo. Rodar: uv run python -m cli.main [--url http://localhost:8000]

Sem --url: roda o agente in-process. Com --url: chama o servidor HTTP.
"""
import uuid

import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

app = typer.Typer()
console = Console()


@app.command()
def chat(url: str | None = typer.Option(None, help="URL do servidor HTTP; vazio = in-process")):
    session_id = str(uuid.uuid4())
    employee_id = typer.prompt("Employee ID", default="E123")
    console.print(Panel(f"[bold]Agente RH/TI[/bold] — sessão {session_id[:8]}… (digite 'sair')"))

    while True:
        q = typer.prompt("\nVocê")
        if q.lower() in ("sair", "exit", "quit"):
            break
        try:
            if url:
                r = httpx.post(f"{url}/chat", json={
                    "question": q, "employee_id": employee_id, "session_id": session_id,
                }, timeout=60)
                data = r.json() if r.status_code == 200 else {"answer": r.json().get("detail", "erro"), "sources": [], "latency_ms": 0}
            else:
                from agent.graph import run_agent
                data = run_agent(q, employee_id, session_id)
        except Exception as e:
            console.print(f"[red]Erro: {e}[/red]")
            continue

        console.print(Markdown(data["answer"]))
        for s in data.get("sources", []):
            console.print(f"  [dim]↳ {s['type']}: {s['ref']}[/dim]")
        console.print(f"  [dim]{data.get('latency_ms', 0)} ms[/dim]")


if __name__ == "__main__":
    app()
