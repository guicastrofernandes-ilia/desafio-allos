# Arquitetura

Detalhes completos em `docs/specs/01-architecture.md`. Resumo executivo aqui.

## Fluxo do agente (LangGraph)

Diagramas unificados em `DIAGRAMS.md` e `docs/specs/01-architecture.md`. Resumo do fluxo:

```
pergunta → guard_input (determinístico) → classify (modelo do provedor)
    ├─ policy  → rag (Chroma k=6, corte por distância, re-query 1x) → synthesize
    └─ oos     → fallback ("não sei" honesto; inclui dado vivo sem acesso)
synthesize (modelo do provedor, citações obrigatórias) → guard_output (judge leve, score<0.7 → fallback) → resposta
```

Checkpointer (`SqliteSaver`, `thread_id` = session): **trilha de auditoria** — estado do grafo por nó é persistido para debug/forense, não é usado como memória conversacional. Multi-turn ativo (referências anafóricas) é fora de escopo; ver ADR 002.

## Principais trade-offs

| Decisão | Trade-off |
|---|---|
| LangGraph vs AgentExecutor | Controle explícito (guardrails como nós, retry por nó) vs menos boilerplate |
| Classifier dedicado vs ReAct livre | Routing auditável e barato vs flexibilidade |
| Modelo leve (planner/juiz) + modelo principal (síntese) vs modelo único | Custo ~10x menor nas etapas auxiliares vs simplicidade; qualidade da síntese justifica |
| Chroma local vs vector DB | Zero infra/reprodutível vs escala; read-only em runtime, ingest = job separado |
| Guardrails no grafo vs framework (NeMo) | Transparência e zero dependência pesada vs robustez; judge adiciona ~300ms ao p95 |
| Judge síncrono vs assíncrono | Segurança (bloqueia antes de responder) vs latência; streaming + judge paralelo é o próximo passo |

## Sob mais carga

- LLM externo satura primeiro (rate limit do provedor) → fila + backoff; modelo leve absorve mais RPS que o principal.
- `uvicorn --workers N` para CPU; Chroma read-only aguenta ~100 qps locais; SQLite checkpointer vira gargalo → Postgres.
- ADR completo com separação em 5 serviços: `docs/specs/04-adr.md`.

## Sob falhas

| Falha | Comportamento |
|---|---|
| Provedor LLM 429/5xx | retry exponencial 3x → 503 com Retry-After |
| Chroma vazio/corrompido | fallback "base indisponível" + sugere contato RH |
| Judge LLM falha | score 0.5 → fallback seguro (fail-closed) |
| Prompt injection | bloqueio determinístico 422, sem chamada LLM |

## Sob custo de LLM

- Routing com modelo leve: só a síntese usa modelo caro.
- `max_tokens` limitado; cache de classify (perguntas repetidas) é otimização seguinte.
- Estimativa: < $5/1000 perguntas (ver docs/specs/03-latency-scale.md).
