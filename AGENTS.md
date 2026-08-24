# AGENTS.md

## Comandos

```bash
uv sync                                        # instalar (uv, não pip/poetry)
uv run python -m rag.ingest                    # OBRIGATÓRIO antes de rodar RAG — sem índice, retrieve falha
uv run uvicorn server.main:app --port 8000     # servidor
uv run python -m cli.main                       # CLI in-process
uv run python -m eval.run_eval [--filter q01] [--category policy]  # harness, gates → exit 1
uv run pytest tests/ -v                         # testes unitários dos guardrails determinísticos
uv run python -m bench.latency                  # p50/p95 → results/
uv run locust -f bench/locustfile.py --host http://localhost:8000 --headless -u 20 -r 2 -t 60s --csv results/load
```

Ordem para verificação completa: ingest → server → eval → bench.

## Armadilhas

- **`.env` obrigatório** com `LLM_API_KEY`. Sem chave, ingest e agente falham. Nunca commitar `.env`.
- **Python 3.14**: `SqliteSaver` exige `sqlite3.connect(..., check_same_thread=False)` — já aplicado em `agent/graph.py`; não remover.
- **Mudou `knowledge_base/`** → rodar `rag.ingest` de novo. Chroma é persistente; não re-indexa sozinho. Índice vive em `.chroma/` (gitignored).
- **`localhost` no macOS resolve IPv6 primeiro** — se server responder 404 HTML genérico, há processo estranho escutando `*:8000`. Verificar `lsof -i :PORT -P`; matar PID IPv6. Já aconteceu duas vezes.
- **Chunking do RAG é por seção markdown (`##`)**, não RecursiveCharacterTextSplitter — `rag/ingest.py:split_markdown_sections`. Seções novas sem header `##` viram um chunk só.
- **Intent é só `policy | oos`**: dado vivo (saldo, ticket) é `oos` → fallback, sem inventar. Ao mexer no classifier, rodar `eval.run_eval` para não quebrar gate de intent (≥0.85).
- **Guardrail de saída é fail-closed**: judge LLM falhando → score 0.5 → fallback. Se respostas virarem fallback genérico de repente, checar quota/chave do provedor primeiro.
- **`results/` é gitignored** — evidências (latency.csv, eval_report.json) são geradas, não commitadas.

## Convenções

- Respostas do agente **sempre pt-BR**; prompts de sistema em pt-BR onde o usuário vê, inglês onde é instrução interna — seguir o padrão existente.
- Toda fonte citada: RAG → `[fonte: arquivo.md]`. Não remover `sources` do estado.
- Modelos trocáveis **só via env** (`MODEL_PLANNER` etc.) — nunca hardcodar nome de modelo fora de `agent/config.py` defaults.
- Nós novos no grafo devem registrar tempo em `state["timings"]` (padrão `_ms(t0)` em `guard_input.py`) — bench depende disso.

## Estrutura (o que muda onde)

| Quer mudar... | Vá em |
|---|---|
| Fluxo/roteamento | `agent/graph.py` (edges condicionais) |
| Regras de bloqueio/injection | `agent/nodes/guard_input.py` (determinístico) |
| Qualidade da resposta final | `agent/nodes/synthesize.py` (prompt) |
| Rigor do judge | `GUARD_OUTPUT_THRESHOLD` env + `guard_output.py` |
| Corpus RAG | `knowledge_base/**.md` + re-ingest |
| Casos de teste do agente | `eval/dataset.jsonl` (27 casos, gates em `run_eval.py`) |

## Specs

`docs/specs/00-05` — decisões de escopo, arquitetura, guardrails, latência/escala, ADR, roteiro de demo. Consultar antes de mudanças estruturais; atualizar spec correspondente se mudar comportamento.
