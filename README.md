# Agente de Suporte a Colaboradores (RH/TI)

Agente de IA com **LangGraph** que responde dúvidas de políticas internas usando **RAG** sobre documentos locais (markdown em `knowledge_base/`).

**Cenário:** suporte a colaboradores (processo interno). **Fonte escolhida:** **A) RAG** — base de conhecimento. Justificativa: o requisito pede indicar fonte/trecho usado, e RAG responde a isso com citação `[fonte: arquivo#seção]`. Perguntas que exijam dado transacional vivo (saldo de um funcionário, status de um ticket) estão fora de escopo e caem em fallback honesto — não acessamos sistemas transacionais.

## Por que RAG neste projeto?

Escolhi **RAG sobre corpus local de markdown** em vez de uma API de dados transacionais. As vantagens técnicas, sob a lente do domínio e do desafio:

### 1. O domínio é conhecimento documental, não estado mutável
As dúvidas prevalentes de RH/TI são **políticas escritas**: direito a férias, regras de fracionamento, valores de benefícios, garantia de equipamentos, SLA de suporte, licença-maternidade. São regras **estáticas e centradas em texto** — exatamente o caso de uso canônico de recuperação de conhecimento. Não há estado transacional vivo a consultar (saldo por funcionário, fila de tickets), então um vector store sobre os documentos resolve a maior parte das perguntas sem tocar sistema externo.

### 2. Fonte e traço de auditoria exigido do desafio
O requisito 5 pede **indicar a fonte usada**. No RAG isso é nativo: cada chunk recuperado leva `metadata.source` com o caminho do arquivo, e o agente é instruído a citar `[fonte: arquivo#seção]`. A resposta expõe `sources` com `ref` + `excerpt` (o trecho real usado). Isso torna a resposta **verificável** — qualquer afirmação pode ser rastreada até o documento de origem — e o `guard_output` confere groundedness (a resposta é suportada pelos docs). Numa API, a "fonte" seria apenas um endpoint consultado, sem o conteúdo textual para auditoria.

### 3. Zero infraestrutura externa e reprodutibilidade
O corpus vive em `knowledge_base/` (6 arquivos markdown, ~30 seções indexadas), e o índice é um **Chroma persistente em `.chroma/`** no próprio repositório. Não há banco, serviço ou vector-db gerenciado: o agente roda com `uv run python -m rag.ingest && uv run uvicorn server.main:app`. O ingest é um **job separado** (fora do request path), então o runtime só faz leitura — sem lock de escrita, sem dependência de disponibilidade de API externa. Reproduzível em qualquer máquina com a mesma base.

### 4. Baixo custo de LLM (vetorização é lenta, mas uma vez)
Para um corpus pequeno (~30 seções), as **embeddings são calculadas uma vez no ingest**, não por request. Em runtime o caminho é: `guard_input` (determinístico, ~0ms) → `classify` (modelo leve) → `retrieve` (Chroma local, ~450ms) → `synthesize` (modelo principal). Ou seja: **2 chamadas de LLM por pergunta** (1 leve + 1 principal). Comparado com um agente tool-calling que planeja e chama rotas dinamicamente, o fluxo RAG é mais barato e mais previsível em latência.

### 5. Latência dominada pelo LLM, não pela recuperação
A medição real (23 amostras, `results/latency_summary.md`) mostra: **p50 = 2515ms, p95 = 3369ms**. O breakdown evidencia que **a recovery é barata** — `rag` ≈ 450ms (Chroma local + embedding de query) contra `synthesize` ≈ 1344ms (LLM principal) e `classify` ≈ 784ms (LLM leve). Como o corpus é pequeno e local, o `retrieve` nunca é o gargalo; o custo está no LLM externo. Isso confirma que a topologia RAG é adequada: a base não escala mal e o foco de otimização é o modelo, não a busca.

### 6. Garantia contra alucinação
Sem tool call para consultar dados vivos, o agente **não tem como inventar** um saldo ou status de ticket. Toda resposta sai de um trecho recuperado, validado pelo `guard_output`; se nenhum trecho é relevante, cai em **fallback honesto** ("não tenho informação suficiente..."). Isso atende o requisito 4 (comportamento claro quando não sabe) e evita alucinar números.

### 7. Trade-off aceito (e documentado)
A contrapartida: perguntas sobre **dado transacional vivo** ("quantos dias o E123 tem", "status do ticket T-1002") ficam **fora de escopo** e caem em fallback. Em produção, isso seria coberto por uma API/tool de dados — e o desenho em `docs/specs/04-adr.md` já prevê um serviço de dados separado (a barreira de um vector store não impede adicionar ferramentas). Para este desafio, onde a maioria das perguntas é de política, RAG puro cobre o caso de uso com máxima rastreabilidade e custo mínimo.

## Setup

```bash
cp .env.example .env          # preencher LLM_API_KEY
uv sync                       # instala dependências
uv run python -m rag.ingest   # indexa knowledge_base/ no Chroma
```

## Executar

Dois processos (2 terminais):

```bash
uv run uvicorn server.main:app --port 8000     # agente HTTP
uv run python -m cli.main                       # CLI in-process
# ou CLI via HTTP: uv run python -m cli.main --url http://localhost:8000
```

### HTTP

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Qual o valor do vale-refeição?", "employee_id": "E123"}'
```

Resposta inclui `answer`, `sources` (trecho RAG), `latency_ms`, `timings` (breakdown por etapa) e header `X-Latency-Breakdown`. Multi-turn: reutilize o `session_id` retornado.

## Medir latência

```bash
uv run python -m bench.latency --url http://localhost:8000
# → results/latency.csv + results/latency_summary.md (p50/p95, 23 perguntas, breakdown)
```

## Evidenciar escala

```bash
uv run locust -f bench/locustfile.py --host http://localhost:8000 \
  -u 20 -r 2 -t 60s --headless --csv results/load
uv run python -m bench.load_report results/load_stats.csv > results/load_test.md
```

## Avaliar qualidade (harness)

```bash
uv run python -m eval.run_eval                  # 27 casos, gates de qualidade
uv run python -m eval.run_eval --category policy
```

Gates: intent ≥ 0.85, citação RAG ≥ 0.90, bloqueio de injection = 1.0. Falha → exit 1.

## Estrutura

| Dir | Conteúdo |
|---|---|
| `agent/` | Grafo LangGraph, nós, guardrails, LLM factory (provedor OpenAI-compatible) |
| `rag/` | Ingest + store Chroma |
| `knowledge_base/` | Políticas em markdown (fonte RAG) |
| `server/` | Endpoint `/chat` |
| `cli/` | CLI interativo |
| `eval/` | Dataset rotulado + harness |
| `bench/` | Latência (p50/p95) + carga (locust) |
| `docs/specs/` | Specs 00-05 + ADR |

## Docs

- `ARCHITECTURE.md` — fluxo, trade-offs, comportamento sob falha/carga/custo
- `docs/specs/04-adr.md` — ADR: dezenas de usuários concorrentes em produção
- `docs/specs/05-demo-script.md` — roteiro de demo com 10 perguntas
