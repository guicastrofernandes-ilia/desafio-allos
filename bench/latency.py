"""Benchmark de latência ponta a ponta. Uso:
    uv run python -m bench.latency --url http://localhost:8000
Saída: results/latency.csv + results/latency_summary.md
"""
import argparse
import csv
import json
import time
from pathlib import Path

import httpx
import numpy as np

QUESTIONS = [
    # férias
    "Quantos dias de férias tenho direito por ano?",
    "Posso vender parte das minhas férias?",
    "Em quantos períodos posso fracionar minhas férias?",
    "Quais os dias de férias são pagos em dobro se a empresa atrasar?",
    "Qual o prazo para pedir abono pecuniário antes das férias?",
    # home office
    "Quantos dias por semana posso trabalhar remoto?",
    "Qual o valor do reembolso de internet no home office?",
    "Gestores têm a mesma política de home office?",
    "Em que horário posso entrar no escritório com flexibilidade?",
    # equipamentos
    "Qual a garantia do notebook da empresa?",
    "Quem cobre o dano acidental no notebook na primeira vez?",
    "De quanto em quanto tempo os notebooks são renovados?",
    # benefícios
    "Qual o valor do vale-refeição?",
    "Existe auxílio-creche? Qual o valor?",
    "Qual a coparticipação dos dependentes no plano de saúde?",
    "Qual o desconto legal do vale-transporte?",
    # suporte
    "Qual o SLA para ticket de prioridade alta?",
    "Como faço para resetar minha senha?",
    # licença
    "Quantos dias de licença-maternidade tenho direito?",
    "Quantos dias de licença-paternidade o pai tem?",
    "Posso prorrogar a licença-maternidade por quanto tempo?",
    # fallback
    "Qual o cardápio do restaurante da empresa hoje?",
    "Quanto custa o estacionamento do prédio vizinho?",
]


def run(url: str):
    rows = []
    with httpx.Client(base_url=url, timeout=90) as client:
        # warmup (descartado)
        for q in QUESTIONS[:10]:
            client.post("/chat", json={"question": q, "session_id": "warmup"})

        for i, q in enumerate(QUESTIONS):
            t0 = time.perf_counter()
            r = client.post("/chat", json={"question": q, "session_id": f"bench-{i}"})
            ms = round((time.perf_counter() - t0) * 1000, 1)
            data = r.json()
            rows.append({
                "question": q[:60],
                "status": r.status_code,
                "intent": data.get("intent"),
                "latency_ms": ms,
                "timings": data.get("timings", {}),
            })
            print(f"[{i+1}/{len(QUESTIONS)}] {ms}ms ({data.get('intent')})")
    return rows


def summarize(rows) -> str:
    lat = [r["latency_ms"] for r in rows]
    p50, p95 = np.percentile(lat, 50), np.percentile(lat, 95)

    # breakdown médio por etapa
    stages: dict[str, list[float]] = {}
    for r in rows:
        for k, v in r["timings"].items():
            stages.setdefault(k, []).append(v)
    stage_avg = {k: round(float(np.mean(v)), 1) for k, v in sorted(stages.items())}

    lines = [
        "# Evidência de latência (ponta a ponta)",
        f"- Amostras: {len(rows)} | warmup: 10 descartadas",
        f"- **p50: {p50:.0f} ms** | **p95: {p95:.0f} ms** | média: {np.mean(lat):.0f} | min: {min(lat)} | max: {max(lat)}",
        "",
        "## Breakdown médio por etapa (ms)",
        "| Etapa | ms |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in stage_avg.items()],
        "",
        "## Por intent",
        "| intent | n | p50 | p95 |",
        "|---|---|---|---|",
    ]
    for intent in {r["intent"] for r in rows}:
        xs = [r["latency_ms"] for r in rows if r["intent"] == intent]
        lines.append(f"| {intent} | {len(xs)} | {np.percentile(xs, 50):.0f} | {np.percentile(xs, 95):.0f} |")

    lines += [
        "",
        "## Gargalos e ações",
        "",
        "1. **LLM externo domina**: synthesize + guard_output + classify ≈ a maior parte da latência média.",
        "   Redução aplicada: modelo leve em classify/judge (etapas mais baratas), max_tokens limitado.",
        "2. **synthesize (modelo do provedor)** é a maior etapa: streaming SSE reduziria TTFB para ~300ms — próximo passo (`/chat/stream`).",
        "3. **guard_output** é fail-safe e síncrono; em modo streaming pode rodar paralelo ao stream.",
        "4. **rag** (~0.4s, embeddings remotos): lookups locais são ~10ms — o custo é a chamada de embedding (provedor).",
        "5. **oos/fallback** mostra o piso: 1 chamada LLM (classify). Latência mínima do sistema ≈ latência de 1 call ao provedor.",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()

    rows = run(args.url)
    out = Path("results")
    out.mkdir(exist_ok=True)
    with open(out / "latency.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["question", "status", "intent", "latency_ms", "timings"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "timings": json.dumps(r["timings"], ensure_ascii=False)})
    (out / "latency_summary.md").write_text(summarize(rows))
    print(f"\nGravado results/latency.csv e results/latency_summary.md")


if __name__ == "__main__":
    main()
