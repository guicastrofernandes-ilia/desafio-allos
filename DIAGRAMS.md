# DIAGRAMS.md — Diagramas do Agente RH/TI

Dois diagramas unificados, fiéis ao código:

- **C4** — visão estrutural única (contexto + containers + componentes do agente).
- **Sequência** — um único fluxo ponta a ponta, com os ramos de decisão do `agent/graph.py`.

> Nota de fidelidade: o roteador de entrada `_route_after_guard` tem o edge `escalate` saindo do `guard_input` (tópico sensível detectado por keyword-match em `guard_input.py:SENSITIVE_TOPICS`), **antes** do `classify`.

---

## 1. C4 — Contexto → Containers → Componentes

```mermaid
flowchart TB
    U(["Colaborador<br/>pt-BR"])

    subgraph CONTEXT["Nível 1 — Contexto"]
        E["Engenheiro / Admin"]
    end

    subgraph AGENT["Nível 2/3 — Container Agente LangGraph<br/>(componentes internos)"]
        direction TB
        GI[guard_input<br/>determinístico]
        CL[classify<br/>Modelo do provedor]
        RAGN[rag<br/>retrieve + grade + re-query]
        SYN[synthesize<br/>Modelo do provedor]
        GO[guard_output<br/>judge leve]
        FB[fallback]
        ES[escalate]
        RB[respond_blocked]

        GI -->|"ok"| CL
        GI -->|"blocked"| RB
        GI -->|"sensitive"| ES
        CL -->|"policy"| RAGN
        CL -->|"oos"| FB
        RAGN -->|"sem docs e sem erro"| FB
        RAGN -->|"docs ok"| SYN
        SYN --> GO
        GO -->|"score >= limiar"| END((END))
        GO -->|"score < limiar"| FB
        FB --> END
        ES --> END
        RB --> END
    end

    subgraph APP["Nível 2 — Containers externos"]
        CLI["CLI Typer<br/>cli/main.py"]
        API["FastAPI /chat<br/>server/main.py"]
        OR["LLM Externo<br/>Provedor LLM<br/>Modelos do provedor"]
        KB[(knowledge_base/**.md)]
        CHROMA[(Chroma .chroma/)]
        SQLITE[(SQLite checkpoint)]
    end

    U -->|"Pergunta (CLI in-process<br/>ou HTTP POST /chat)"| CLI
    U -->|"HTTP POST /chat"| API
    API -->|"invoca"| CL
    CLI -.->|"in-process (opcional)"| CL
    E -->|"ingest de políticas"| KB
    E -->|"roda eval harness"| AGENT
    AGENT --> CHROMA
    AGENT --> KB
    SYN --> OR
    CL --> OR
    GO --> OR
    AGENT <--> SQLITE
```

**Componentes (fonte):**
- `guard_input` — tamanho, idioma pt-BR, PII, prompt-injection; keyword de tópico sensível → `escalate`.
- `classify` — intent: `policy | oos`; JSON inválido → `oos` (fallback seguro, não inventa fonte).
- `rag` — top-k=6, corte `MAX_DISTANCE=1.6`, top-3 no contexto; retry 1x se docs ruins.
- `synthesize` — compõe pergunta + docs; exige citação de fonte.
- `guard_output` — LLM-judge de groundedness; falha → fallback determinístico.
- `fallback` / `escalate` / `respond_blocked` — respostas fixas seguras; **pulam o judge**.

---

## 2. Sequência — Fluxo ponta a ponta (com todos os ramos)

```mermaid
sequenceDiagram
    autonumber
    participant U as Colaborador
    participant A as Agent LangGraph
    participant R as RAG/Chroma
    participant L as LLM (Provedor)

    U->>A: POST /chat {question, session_id}
    Note over A: guard_input (determinístico ~0ms)
    alt bloqueado (idioma/tamanho/injection)
        A-->>U: 422 {answer: block_reason, blocked:true} → respond_blocked
    else sensível (keyword em SENSITIVE_TOPICS)
        A-->>U: escalate → "contate o RH (ramal 4400 / rh@empresa.example)"
        Note over A: resposta fixa confidencial. Pula o judge. END.
    else ok
        A->>L: classify(question) → intent
        alt intent = oos
            A-->>U: fallback "não tenho essa informação" (não alucina)
        else intent = policy
            A->>R: retrieve(question, k=6, corte dist <= 1.6)
            R-->>A: top-3 chunks (docs) + sources[type=rag]
            Note over A: sem docs bons após 1 retry → fallback
            A->>L: synthesize (pergunta + docs) → resposta com [fonte]
        end
        A->>L: guard_output judge (groundedness) → {"score":0-1}
        alt score >= limiar (senão 0.5 se judge falhar — fail-closed)
            A-->>U: 200 {answer, sources, timings, latency_ms}
        else score < limiar
            A-->>U: "Não consegui validar a resposta com as fontes..." (fallback seguro)
        end
    end
```

**Ramos de decisão (fonte):**
- `guard_input` → `respond_blocked` | `escalate` | `classify` (`_route_after_guard`, graph.py:19).
- `classify` → `policy`→rag | `oos`→fallback (`_route_after_classify`, graph.py:24).
- `rag` → sem docs→fallback | docs ok→synthesize (`_route_after_rag`, graph.py:32).
- `synthesize` → `guard_output` (judge) → END ou fallback (fail-closed).

---

## Referência rápida dos fluxos e suas decisões

| Fluxo | Intent/edge | Entrada | Saída | Fonte citada |
|---|---|---|---|---|
| Política | `policy` | dúvida de regra | resposta + `[fonte]` | RAG |
| Dado vivo fora do escopo | `oos` | saldo/ticket de funcionário | "não tenho" + contato RH | nenhuma |
| OOS/fallback | `oos` | fora do escopo | "não sei" honesto | nenhuma |
| Escalonar | keyword sensível | tema pessoal | contato humano | nenhuma |
| Block entrada | guardrail | injection/idioma | 422 | nenhuma |
| Judge falha | guardrail | score < limiar | fallback seguro | nenhuma |
