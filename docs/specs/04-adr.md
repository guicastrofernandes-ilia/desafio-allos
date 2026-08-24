## ADR 002 — Checkpointer mantido para auditoria (não memória conversacional)

**Decisão (2026-08-25):** o SQLite `SqliteSaver` permanece no runtime como **trilha de auditoria** — cada nó executado grava um checkpoint chaveado por `thread_id=session_id`, permitindo inspecionar o estado por `trace_id` após a execução e sobreviver a restarts. **Não** é usado como memória conversacional: os nós `classify`/`synthesize` recebem apenas a pergunta atual; referências anafóricas multi-turn são **fora de escopo** nesta entrega.

**Motivação:** alto valor de debug/forense (rastreio de erros de judge, duplicação de fontes) com custo baixo; evitar custo de storage/tokens de janelas de histórico sem necessidade de negócio. Se multi-turn virar requisito, reaproveitar os checkpoints existentes injetando síntese do histórico (janela deslizante) no prompt — sem mudança de storage.

---

# ADR 001 — Separação de responsabilidades para produção (dezenas de usuários concorrentes)

## Status

Proposto — 2026-08-24

## Contexto

Implementação atual: monólito FastAPI + LangGraph in-process, Chroma local, SQLite checkpointer, mock API no mesmo repo. Suficiente para demo. Para dezenas de usuários concorrentes em produção, limites: rate limit do provedor LLM, lock do SQLite, single point of failure, ausência de isolamento entre camadas.

## Decisão

Separar em 5 responsabilidades com limites claros:

```
cliente ─▶ [API Gateway / LB]
              │
        ┌─────▼──────┐      ┌───────────────┐
        │ chat-api   │─────▶│ llm-gateway    │ (fila, rate limit, retry, cache)
        │ (stateless │      │ (fila interna) │
        │  N pods)   │      └───────┬────────┘
        └──┬─────┬───┘              │ Provedor de LLM
           │     │
   ┌───────▼─┐ ┌─▼────────┐
   │ rag-    │ │ checkpointer│
   │ service │ │ (Postgres)  │
   │(Qdrant) │ └────────────┘
   └─────────┘
```

1. **chat-api (stateless):** recebe `/chat`, roda grafo LangGraph, sem estado local — sessão no Postgres checkpointer. Escala horizontal (HPA por CPU/latência).
2. **llm-gateway:** ponto único de saída p/ LLM. Fila (Redis/SQS), semaphore por modelo, retry/backoff centralizado, cache de respostas idempotentes (classify), circuit breaker. Protege rate limit e dá observabilidade de custo.
3. **rag-service:** Qdrant/pgvector dedicado; ingest como job versionado (índice imutável, blue-green por coleção).
4. **checkpointer Postgres:** substitui SQLite; `thread_id` particionado; retention policy.

## Riscos e mitigações

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Rate limit LLM (429) | Alta | Alto | llm-gateway com fila + backoff; modelo leve absorve pico; cache de classify |
| Latência LLM degrada p95 | Alta | Médio | streaming; timeout 30s + fallback "indisponível"; modelo fallback (segunda provider) |
| Alucinação em política crítica | Média | Alto | guard_output obrigatório; tópicos sensíveis → escalate humano; auditoria de traces |
| Prompt injection via pergunta | Média | Alto | guard_input blocklist; sanitização de docs ingeridos; LLM-judge |
| Dados PII em logs/traces | Média | Alto | mascaramento em guard_input; LangSmith com redaction; retention curto |
| Falha do vector store | Baixa | Médio | réplica read-only; fallback "base indisponível" |
| Custo LLM explode sob carga | Média | Médio | budget alerts; cache; routing com modelo leve; cap de re-síntese (1x) |
| SQLite lock (se não migrar) | Alta | Alto | migrar checkpointer p/ Postgres antes de >10 usuários |
| Deploy quebra índice RAG | Baixa | Médio | coleção versionada; rollback = apontar p/ coleção anterior |

## Consequências

- **Positivas:** escala independente por camada; rate limit protegido; observabilidade por serviço; deploy sem derrubar sessões.
- **Negativas:** 5 deployables vs 1; necessidade de Redis/Postgres/Qdrant; latência de rede entre serviços (+10-50ms); complexidade operacional.
- **Não fazer agora:** service mesh, multi-região, fine-tuning — prematuro p/ dezenas de usuários.
