# Spec 03 — Latência e Escala

## Metodologia de latência

- **Conjunto:** ≥ 20 perguntas representativas (21 RAG / policy, 2 fallback) — mesmo dataset do harness, categoria ≠ adversarial.
- **Medição:** ponta a ponta, cliente → resposta completa. Script `bench/latency.py` chama `POST /chat` sequencialmente, warmup 10 reqs descartadas.
- **Percentis:** p50, p95, média, min, max — `numpy.percentile`.
- **Saída:** `results/latency.csv` (pergunta, intent, ms) + `results/latency_summary.md` (tabela + análise de gargalos).

### Breakdown por etapa (instrumentação)

Cada nó registra tempo no state; resposta inclui `latency_breakdown` no header `X-Latency-Breakdown` (JSON) ou campo opcional:

| Etapa | Medido (média) | Otimização |
|---|---|---|
| guard_input | <1ms | determinístico |
| classify | ~880ms | modelo do provedor (leve), prompt curto, JSON mode |
| rag retrieve | ~440ms | Chroma local; embeddings remotos dominam |
| synthesize | ~1570ms | modelo do provedor; **streaming** reduz TTFB p/ ~300ms |
| guard_output | ~1400ms | paralelo ao stream; skip em fallback |
| **p50 medido** | **~4400ms** | |
| **p95 medido** | **~6200ms** | |

Medido em 2026-08-24 via provedor externo (rede + fila do provedor inflam vs estimativa original de 2s/4s — LLM é 93% do tempo; ver `results/latency_summary.md`).

### Reduções de latência aplicadas

1. Streaming de tokens (SSE no `/chat/stream`) — TTFB << latência total.
2. Modelo leve em classify/judge.
3. Embeddings persistidos — ingest é job separado, nunca no request path.
4. `max_tokens` limitado no synthesize (600).
5. HTTP keep-alive + cliente httpx async com pool.

## Metodologia de escala

- **Ferramenta:** locust (`bench/locustfile.py`).
- **Cenário:** rampa 1 → 20 usuários concorrentes, 60s hold, distribuição de perguntas = dataset.
- **Métricas:** RPS, p50/p95 sob carga, taxa de erro, throughput.
- **Limitante esperado:** rate limit do provedor (tier) → evidência: RPS máximo antes de 429, comportamento de fila/retry.

**Medido em 2026-08-25** (20 usuários, rampa 2/s, 60s): 177 requisições, **0 falhas**, p50=3700ms, p95=9500ms, p99=14000ms, max=16115ms — ver `results/load_test.md`. Sem rate limit 429 observado neste volume; p95/max cresceram ~30-100% vs. teste com 10 usuários, indicando fila crescente no LLM externo como primeiro sinal de saturação (ainda sem erro visível ao cliente).

### Comportamento sob carga (análise)

| Componente | Gargalo | Mitigação |
|---|---|---|
| FastAPI/uvicorn | 1 worker = CPU-bound só no parse; I/O-bound na prática | `uvicorn --workers N` (CPU cores) |
| LLM externo | rate limit + latência compartilhada | fila (asyncio.Semaphore) + backoff; modelo leve absorve mais RPS |
| Chroma read | thread-safe p/ leitura; ~100 qps local | shard ou Qdrant se > 100 qps |
| SQLite checkpointer | lock de escrita por thread_id | Postgres checkpointer em produção |

### Evidência numérica a entregar

`results/load_test.md`: tabela (usuários × RPS × p50/p95 × erros) + interpretação: ponto de saturação, qual componente satura primeiro, o que muda com 2x carga.

## Custos (estimativa p/ 1000 perguntas)

| Modelo | Uso | Custo est. |
|---|---|---|
| Modelo leve (classify+judge) | ~2k calls × 300 tok | < $0.05 |
| Modelo principal (síntese) | 1k calls × 800 tok in / 300 out | ~$3-5 |
| embeddings | corpus único, 30 docs | < $0.01 |

Trade-off registrado: síntese com modelo principal dobra custo vs tudo-leve; qualidade em políticas ambíguas justifica (avaliado no harness).
