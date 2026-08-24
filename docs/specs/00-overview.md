# Spec 00 — Visão Geral

## Contexto

Desafio técnico: agente de IA (LangChain/LangGraph) para processo interno.

**Cenário escolhido:** Assistente de suporte a colaboradores de RH/TI — responde dúvidas sobre políticas internas (férias, benefícios, home office, equipamentos, licenças, suporte de TI).

**Fonte de dados:** **A) RAG** sobre corpus local de políticas internas (markdown em `knowledge_base/`). Optou-se por RAG (não API) por responder melhor ao requisito de indicar fonte/trecho usado — cada resposta cita `[fonte: arquivo#seção]`. Perguntas que exijam dado transacional vivo (saldo de um funcionário, status de um ticket) estão fora de escopo e caem em fallback honesto.

## Escopo

| Item | Incluído | Fora de escopo |
|---|---|---|
| Agente LangGraph | Sim | — |
| RAG com citação de trecho | Sim | — |
| Guardrails de entrada/saída | Sim | — |
| Harness de avaliação | Sim | Fine-tuning |
| HTTP (FastAPI) + CLI | Sim | UI web |
| Benchmark p50/p95 (≥20 perguntas) | Sim | — |
| Teste de carga | Sim | Deploy em cloud |
| Multi-turn (memória de sessão) | Sim (checkpointer) — **uso atual: auditoria/rastreabilidade**, não memória conversacional ativa | Auth/SSO |

## Entregáveis (mapa do repo)

| Entregável do desafio | Local |
|---|---|
| Código reproduzível | raiz + `pyproject.toml` + `.env.example` |
| README | `README.md` |
| Arquitetura + trade-offs | `ARCHITECTURE.md` |
| Evidência de latência | `results/latency.csv` + `results/latency_summary.md` |
| Evidência de escala | `results/load_test.md` |
| Roteiro de demo | `docs/specs/05-demo-script.md` |
| ADR | `docs/specs/04-adr.md` |

## Stack decidida

| Camada | Escolha | Alternativa rejeitada | Motivo |
|---|---|---|---|
| Orquestração | **LangGraph** (grafo com roteamento condicional) | AgentExecutor clássico | Controle explícito de fluxo, retry, guardrails como nós; checkpointer nativo p/ auditoria |
| LLM | **provedor de LLM OpenAI-compatible** (modelo leve (planner/juiz) + modelo principal (síntese)) | Anthropic direto / Ollama | Uma chave, vários modelos; fácil trocar modelo via env var sem mudar código |
| Embeddings | embeddings do provedor via endpoint OpenAI-compatible | Embeddings locais (sentence-transformers) | Sem GPU garantida na máquina do avaliador; reprodutibilidade |
| Vector store | **Chroma** (persistente, em disco) | FAISS / pgvector | Zero infra externa; persiste entre runs; suficiente p/ corpus pequeno |
| Guardrails | Nós determinísticos no grafo + LLM-judge leve para saída | NeMo Guardrails / Guardrails AI lib | Dependências pesadas; grafo já dá estrutura — guardrails como nós são mais transparentes |
| Harness | **LangSmith** (opcional) + script próprio de avaliação em dataset rotulado | RAGAS puro | Script próprio = zero SaaS obrigatório; LangSmith plugável via env |
| Servidor | FastAPI + uvicorn | Flask | Async nativo; OpenAPI grátis |
| Testes carga | **locust** | k6 | Python, mesmo ecossistema |
| Package manager | **uv** | poetry/pip | Rápido, lockfile, já instalado |

## Requisitos não-funcionais

- Respostas sempre em **português (pt-BR)**.
- Toda resposta RAG cita **fonte e trecho** (`[fonte: arquivo#seção]`).
- Comportamento explícito quando: (a) não sabe, (b) fonte falha, (c) guardrail bloqueia.
- Sem secrets no repo; `.env.example` documenta todas as variáveis.

## Riscos principais

1. **Latência de LLM externo** domina p50/p95 → mitigar com modelo leve no planner, cache de embeddings, streaming.
2. **Corpus pequeno** pode gerar respostas fora do escopo → guardrail de relevância + fallback "não sei".
3. **Rate limit do provedor de LLM** no teste de carga → retry com backoff + evidência coletada em concorrência moderada.
