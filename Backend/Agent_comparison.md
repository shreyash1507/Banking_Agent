Here's the breakdown, mapped directly to your five agents:

---

### Pricing reference (Bedrock on-demand, per 1M tokens)

Claude Opus 4.6: $5 input / $25 output — Claude Sonnet 4.6: $3 / $15 — Claude Haiku 4.5: $1 / $5. Nova Micro: $0.035 / $0.14 — Nova Lite: $0.06 / $0.24 — Nova Pro: $0.80 / $3.20.

---

### Agent-by-agent recommendations

---

#### 1. Intent Classifier — Nova Micro or Nova Lite

| | |
|---|---|
| *Cost* | Extremely low — $0.035/$0.14 per 1M tokens |
| *Latency* | Fastest available on Bedrock |
| *Accuracy* | Sufficient — classification is a constrained output task |

For high-volume simple text tasks like classification, extraction, and routing, Nova Micro is hard to beat on cost. Your intent classifier outputs a fixed enum — POLICY, LOAN, FRAUD — with a confidence score. That is exactly the kind of constrained task where a frontier model is overkill and expensive.

Always benchmark Nova Micro first. If quality is insufficient, try Nova Lite. Only escalate to Claude Haiku when cheaper options demonstrably fail your quality requirements.

*Recommendation:* Start with Nova Micro. If multi-intent queries (POLICY + FRAUD in one message) fail to classify correctly, move to Nova Lite.

---

#### 2. Task Decomposer — Claude Haiku 4.5

| | |
|---|---|
| *Cost* | Low — $1/$5 per 1M tokens |
| *Latency* | Fast |
| *Accuracy* | High for structured reasoning tasks |

Decomposition requires understanding query nuance and producing a correctly ordered, logically sound subtask list. Nova Micro will hallucinate structure here. You need a model that reasons, not just pattern-matches. Haiku 4.5 delivers near-frontier performance matching Claude Sonnet 4's capabilities in coding and agent tasks at substantially lower cost and faster speeds.

*Recommendation:* Claude Haiku 4.5. It's the sweet spot — capable enough for structured reasoning, cheap enough to run on every decomposition call.

---

#### 3. Orchestrator — Claude Sonnet 4.6

| | |
|---|---|
| *Cost* | Mid — $3/$15 per 1M tokens |
| *Latency* | Medium (tool-calling loop adds turns) |
| *Accuracy* | High — judgment, retry logic, tool selection |

The orchestrator is your most demanding agent. It's running a tool-calling loop, exercising judgment on whether to retry, when to escalate, and whether the domain agent's result actually answered the query. This needs a model with genuine reasoning capability. Nova Pro scores 10-12% lower than Claude Sonnet on general benchmarks — for mid-complexity tasks Nova Pro is competitive with Claude Haiku, not Sonnet. That gap matters here because orchestration failures cascade.

*Recommendation:* Claude Sonnet 4.6. Don't cut cost here — a bad orchestration decision is more expensive than the token price difference.

---

#### 4. Policy RAG Agent — Claude Haiku 4.5 (standard) / Claude Sonnet 4.6 (complex)

| | |
|---|---|
| *Cost* | Low to mid |
| *Latency* | Fast to medium |
| *Accuracy* | High — policy language is precise, errors are high-stakes |

RAG agents have two cost levers: the retrieval (your vector DB, not the LLM) and the generation (reading retrieved chunks + producing an answer). The generation step with Haiku 4.5 handles most policy Q&A well since the context is provided — the model just needs to read and synthesize, not reason from scratch.

However, policy documents in banking are often dense and exception-heavy. For queries like "does the prepayment penalty apply if I switch from floating to fixed within the first 3 years?" — Haiku may miss the exception. Use Sonnet as a fallback on low-confidence outputs.

*Recommendation:* Claude Haiku 4.5 as default, with a confidence threshold that escalates to Claude Sonnet 4.6. For RAG applications this single change often delivers 30-50% cost reduction.

---

#### 5. Loan Eligibility RAG Agent — Claude Sonnet 4.6

| | |
|---|---|
| *Cost* | Mid — $3/$15 per 1M tokens |
| *Latency* | Medium |
| *Accuracy* | Highest needed — numerical reasoning + rule application |

Loan eligibility is harder than policy lookup. The model must apply retrieved rules against user-provided parameters — income, CIBIL score, tenure, loan amount — and reason about threshold conditions, exceptions, and combined criteria. This is where Haiku starts making arithmetic or conditional errors. Sonnet handles multi-criteria numerical reasoning reliably.

*Recommendation:* Claude Sonnet 4.6 as default. Don't use Haiku here without extensive evals — an incorrect eligibility answer in a banking context is a liability.

---

### Summary table

| Agent | Model | Input / 1M | Output / 1M | Why |
|---|---|---|---|---|
| Intent Classifier | Nova Micro | $0.035 | $0.14 | Constrained output, high volume, no reasoning needed |
| Task Decomposer | Claude Haiku 4.5 | $1 | $5 | Structured reasoning, not heavy judgment |
| Orchestrator | Claude Sonnet 4.6 | $3 | $15 | Tool-calling loop, judgment, cascading risk |
| Policy RAG | Haiku 4.5 → Sonnet 4.6 | $1→$3 | $5→$15 | Tiered on complexity |
| Loan Eligibility RAG | Claude Sonnet 4.6 | $3 | $15 | Numerical + conditional reasoning, high stakes |

---