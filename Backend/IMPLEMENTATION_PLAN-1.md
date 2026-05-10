# Guardrails & Constraints — Implementation Plan

> Project: Groq API (Llama models) + ChromaDB RAG + multi-agent orchestrator
> Approach: config-driven — all thresholds and rules in `config/guardrails.yaml`, no hardcoded values in guard classes

---

## Config File — `banking_agents/config/guardrails.yaml`

Single source of truth. Loaded once at startup in `banking_agents/main.py`, same pattern as `intents.yaml` and `orchestrator.yaml`.

```yaml
input:
  min_length: 10
  max_length: 2000
  injection_patterns:
    - "ignore previous instructions"
    - "ignore all instructions"
    - "you are now"
    - "act as"
    - "pretend you are"
    - "jailbreak"

orchestrator:
  max_iterations: 5
  max_subtasks: 4
  fallback_message: "I'm having trouble completing your request. Please try rephrasing."

rag:
  hard_distance_threshold: 1.2
  soft_distance_threshold: 0.9
  no_result_message: "I don't have sufficient information in our documents to answer this. Please contact your bank directly."
  low_confidence_disclaimer: "This answer is based on partial matches. Please verify with a bank representative."

output:
  empty_response_fallback: "I wasn't able to generate a response. Please try again."
  intent_disclaimers:
    LOAN_ELIGIBILITY: "This assessment is indicative only. Final loan eligibility is subject to bank verification and approval."
```

---

## Constraints

Constraints are operational limits — they control cost, prevent runaway loops, and handle Groq API failures. All values come from `guardrails.yaml`.

### Orchestrator Loop Constraints — inline in `orchestrator.py`

| Constraint | Config key | What it prevents |
|---|---|---|
| Max iterations | `orchestrator.max_iterations` | Infinite tool-calling loop, runaway Groq cost |
| Max subtasks | `orchestrator.max_subtasks` | TaskDecomposer returning 10+ tasks and flooding domain agents |

Both already exist as hardcoded `MAX_ITERATIONS = 3` — just replace with config reads (detailed in wiring section below).

### Groq API Error Constraints — inline in `orchestrator.py`

The current orchestrator has a bare `except Exception as e: raise e`. Replace with typed Groq error handling:

```python
import groq

try:
    response = self.client.chat.completions.create(
        model=self.model_id,
        messages=messages,
        tools=self.tools_schema,
        tool_choice="auto",
        temperature=0.2,
        timeout=guardrails_config["per_hop_timeout_seconds"],  # ← new
    )
except groq.RateLimitError:
    raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")
except groq.APITimeoutError:
    return AgentResponse(response=self.fallback_msg, context=context)
except groq.APIConnectionError:
    raise HTTPException(status_code=503, detail="Service temporarily unavailable.")
```

Add `per_hop_timeout_seconds` to the `orchestrator` section of `guardrails.yaml`:

```yaml
orchestrator:
  max_iterations: 5
  max_subtasks: 4
  per_hop_timeout_seconds: 30
  fallback_message: "I'm having trouble completing your request. Please try rephrasing."
```

This covers three distinct failure modes:
- **RateLimitError** — Groq free tier throttling (30 RPM) — surface as 429 to caller
- **APITimeoutError** — a single Groq hop hung past `per_hop_timeout_seconds` — return graceful fallback, don't crash
- **APIConnectionError** — network/infrastructure issue — surface as 503

### What is NOT constrained (intentionally)

- **Token budget per query** — not needed for a demo; Groq's own rate limits are the backstop
- **Session rate limiting** — out of scope for bare minimum
- **Per-session history size** — the in-memory store handles this naturally for a demo

---

## Guard Classes

### 1. `guardrails/input_validator.py` — `InputValidator`

**What it checks:**

| Check | Rule | Action |
|---|---|---|
| Query length | `min_length ≤ len(query) ≤ max_length` | Raise `HTTPException(400)` |
| Prompt injection | Case-insensitive match against `injection_patterns` list | Raise `HTTPException(400)` with generic refusal |

**How it reads config:**
```python
class InputValidator:
    def __init__(self, config: dict):
        self.min_length = config["min_length"]
        self.max_length = config["max_length"]
        self.injection_patterns = [p.lower() for p in config["injection_patterns"]]

    def validate(self, query: str) -> None:
        # length check, then injection scan
```

**Where it runs:** `banking_agents/main.py` chat endpoint, before session lookup.

---

### 2. Orchestrator iteration cap — inline in `orchestrator.py`

The orchestrator already has `MAX_ITERATIONS = 3` hardcoded. Replace it with a value read from `guardrails_config`.

No separate class needed — just pass the config section into `OrchestratorAgent.__init__` and read `config["max_iterations"]` and `config["max_subtasks"]` there.

**Changes to `orchestrator.py`:**
- `__init__` receives `guardrails_config: dict` (the `orchestrator` section)
- `MAX_ITERATIONS` replaced by `self.max_iterations = guardrails_config["max_iterations"]`
- After `decompose_task` returns: truncate task list to `guardrails_config["max_subtasks"]`
- `fallback_msg` at loop exhaustion replaced by `guardrails_config["fallback_message"]`

**Where it runs:** Inside the existing `while` loop in `OrchestratorAgent.run()`.

---

### 3. `guardrails/rag_guard.py` — `RAGGuard`

The most important guardrail for a banking RAG system — prevents hallucinated answers when retrieved docs are irrelevant.

ChromaDB returns L2 distances. Lower = more similar.
- `< soft_threshold` → strong match, proceed normally
- `soft_threshold – hard_threshold` → weak match, proceed with disclaimer appended
- `> hard_threshold` or zero results → block LLM call entirely, return `no_result_message`

**How it reads config:**
```python
class RAGGuard:
    def __init__(self, config: dict):
        self.hard_threshold = config["hard_distance_threshold"]
        self.soft_threshold = config["soft_distance_threshold"]
        self.no_result_message = config["no_result_message"]
        self.disclaimer = config["low_confidence_disclaimer"]

    def check(self, retrieved_docs: list[dict]) -> tuple[bool, str | None]:
        # Returns (proceed, disclaimer_or_block_message)
```

**Where it runs:** In `PolicyRAGAgent.answer()` and `LoanEligibilityRAGAgent.answer()`, after `BaseRAG.retrieve()` returns and before the Groq call. If `proceed=False`, return the block message immediately without calling the LLM.

---

### 4. `guardrails/output_validator.py` — `OutputValidator`

**What it checks:**

| Check | Rule | Action |
|---|---|---|
| Empty response | Blank or whitespace | Return `empty_response_fallback` from config |
| Intent disclaimer | `intent` key present in `intent_disclaimers` | Append configured disclaimer string |

**How it reads config:**
```python
class OutputValidator:
    def __init__(self, config: dict):
        self.fallback = config["empty_response_fallback"]
        self.intent_disclaimers = config["intent_disclaimers"]

    def validate(self, response: str, intent: str | None) -> str:
        if not response or not response.strip():
            return self.fallback
        if intent and intent in self.intent_disclaimers:
            response += f"\n\n{self.intent_disclaimers[intent]}"
        return response
```

**Where it runs:** `banking_agents/main.py` chat endpoint, on `agent_response.response` before building `ChatResponse`.

---

## Wiring — What Changes in Existing Files

### `banking_agents/main.py`

```python
# Load guardrails config (add alongside existing config loads)
guardrails_path = os.path.join(config_dir, "guardrails.yaml")
with open(guardrails_path) as f:
    guardrails_config = yaml.safe_load(f)

# Instantiate guards once at startup
input_validator = InputValidator(guardrails_config["input"])
output_validator = OutputValidator(guardrails_config["output"])

# Pass orchestrator section into OrchestratorAgent
orchestrator = OrchestratorAgent(
    intents_config=intents_data,
    orchestrator_config=orchestrator_data,
    guardrails_config=guardrails_config["orchestrator"],  # ← new
)

# In the chat endpoint:
input_validator.validate(request.query)          # raises 400 on fail
agent_response = orchestrator.run(user_query, context)
final_response = output_validator.validate(
    agent_response.response,
    context.current_intent
)
```

### `banking_agents/agents/reusable/orchestrator.py`

```python
def __init__(self, intents_config, orchestrator_config, guardrails_config):
    ...
    self.max_iterations = guardrails_config["max_iterations"]
    self.max_subtasks   = guardrails_config["max_subtasks"]
    self.fallback_msg   = guardrails_config["fallback_message"]

# In run():
while iteration < self.max_iterations:   # was MAX_ITERATIONS = 3

# After decompose_task result:
tasks = tasks[:self.max_subtasks]
```

### `banking_agents/agents/domain/policy_rag_agent.py` and `loan_eligibility_rag_agent.py`

```python
# In __init__:
self.rag_guard = RAGGuard(guardrails_config["rag"])   # pass config section in

# In answer():
retrieved_docs = self.rag.retrieve(task, n_results=3)
proceed, message = self.rag_guard.check(retrieved_docs)
if not proceed:
    return message
# ... rest of LLM call, appending message as disclaimer if not None
```

---

## Files to Create / Modify

| File | Action |
|---|---|
| `banking_agents/config/guardrails.yaml` | Create |
| `banking_agents/guardrails/__init__.py` | Create (empty) |
| `banking_agents/guardrails/input_validator.py` | Create |
| `banking_agents/guardrails/rag_guard.py` | Create |
| `banking_agents/guardrails/output_validator.py` | Create |
| `banking_agents/main.py` | Modify — load config, wire guards |
| `banking_agents/agents/reusable/orchestrator.py` | Modify — replace hardcoded `MAX_ITERATIONS` |
| `banking_agents/agents/domain/policy_rag_agent.py` | Modify — add `RAGGuard` |
| `banking_agents/agents/domain/loan_eligibility_rag_agent.py` | Modify — add `RAGGuard` |

## Implementation Order

1. `config/guardrails.yaml` — define all values first
2. `guardrails/rag_guard.py` — highest value, prevents hallucination
3. Wire `RAGGuard` into both domain agents
4. `guardrails/input_validator.py` — wire into `main.py`
5. `guardrails/output_validator.py` — wire into `main.py`
6. `orchestrator.py` — replace `MAX_ITERATIONS` with config-driven value
