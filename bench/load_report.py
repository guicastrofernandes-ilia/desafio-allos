"""Gera results/load_test.md a partir do CSV do locust.
Uso: uv run python -m bench.load_report results/load_stats.csv
"""
import csv
import sys
from pathlib import Path


def main(csv_path: str):
    rows = [r for r in csv.DictReader(open(csv_path)) if r["Name"] == "/chat" or r["Type"] == "Aggregated"]
    if not rows:
        print("Nenhuma linha /chat no CSV", file=sys.stderr)
        sys.exit(1)
    r = rows[0]
    print(f"""# Evidência de escala (locust)

| Métrica | Valor |
|---|---|
| Requisições | {r['Request Count']} |
| Falhas | {r['Failure Count']} |
| RPS mediano | {r.get('Requests/s', '-')} |
| p50 (ms) | {r.get('50%', '-')} |
| p95 (ms) | {r.get('95%', '-')} |
| p99 (ms) | {r.get('99%', '-')} |
| Max (ms) | {r.get('Max Response Time', '-')} |

## Interpretação

(preencher após rodada: ponto de saturação observado, primeiro gargalo — rate limit
do provedor de LLM vs CPU local — e o que muda dobrando a carga; ver docs/specs/03-latency-scale.md)
""")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/load_stats.csv")
