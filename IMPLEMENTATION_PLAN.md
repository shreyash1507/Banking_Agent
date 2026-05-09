# Implementation Plan: Complete the Banking Agent System

## Overview

This document covers two tracks of work:
1. **Completing pending implementations** — stub files, RAG pipeline, tool registry
2. **Adding automated constraints handling and guardrails** — validation, safety, cost control

Fraud use case is excluded. All changes are additive and backward-compatible with the existing orchestrator/RAG architecture.

---

## Track 1: Pending Implementations

### 1.1 Base Agent Class — `agents/base.py`

Currently empty. Every domain agent duplicates Bedrock client setup and response parsing.

**What to implement:**
- `BaseAgent` abstract class with `client`, `model_id` attributes initialized once
- Abstract `answer(task: str) -> str` method
- Shared `_call_bedrock(messages, system_prompt, temperature)` helper that wraps `client.converse()` and handles Bedrock exceptions uniformly
- All domain agents (`PolicyRAGAgent`, `LoanEligibilityRAGAgent`) inherit from this

---

### 1.2 Tool Registry — `tools/registry.py`

Planned in `yaml_config_plan.md` but not implemented. Currently the Orchestrator does its own `importlib` loading inline.

**What to implement:**
- `ToolRegistry` class that reads `orchestrator.yaml` at init
- `load_all()` — uses `importlib.import_module` + `getattr` to instantiate each tool class
- `get_tool(name)` — returns the live instance
- `get_bedrock_schema()` — returns the full `toolConfig` dict for Bedrock's `converse()` call, generated from YAML fields (`name`, `description`, `input_property`)
- `execute(tool_name, input_data)` — single dispatch point replacing the `if/elif` block in the Orchestrator
- Orchestrator refactored to delegate entirely to `ToolRegistry` (removes inline `importlib` and `if/elif` routing)

---

### 1.3 Document Search Tool — `tools/document_search.py`

**What to implement:**
- `DocumentSearchTool` class with `search(query, collection_name, n_results)` method
- Wraps `BaseRAG.retrieve()` with a clean interface
- Returns structured results: `[{content, source_doc, similarity_score}]`
- Used by `PolicyRAGAgent` and `LoanEligibilityRAGAgent` instead of calling `BaseRAG` directly — decouples domain agents from ChromaDB internals

---

### 1.4 Eligibility Checker Tool — `tools/eligibility_checker.py`

**What to implement:**
- `EligibilityChecker` class with deterministic rule evaluation — no LLM involvement
- `check(applicant_data: dict, loan_type: str) -> EligibilityResult`
- `EligibilityResult` dataclass: `{eligible: bool, passed_rules: list, failed_rules: list, reason: str}`
- Rules sourced from a YAML config (`config/eligibility_rules.yaml`) — e.g., min CIBIL score, min income, age range, max loan-to-value ratio per loan type
- `LoanEligibilityRAGAgent` calls this first; LLM only explains the result, never overrides it

**`config/eligibility_rules.yaml` structure:**
```yaml
home_loan:
  min_cibil_score: 700
  min_income_monthly: 25000
  min_age: 21
  max_age: 65
  max_ltv_ratio: 0.80

personal_loan:
  min_cibil_score: 720
  min_income_monthly: 20000
  min_age: 21
  max_age: 60
```

---

### 1.5 RAG Ingest Modules — `rag/policy/ingest.py` and `rag/loan/ingest.py`

Currently empty. The ChromaDB collections are never populated, so RAG retrieval returns nothing.

**What to implement (both modules, same pattern):**
- `ingest_documents(docs_folder: str)` function
- Reads `.docx` files using `python-docx`
- Chunks text (sliding window: 500 tokens, 100 token overlap)
- Calls `BaseRAG.ingest(documents, metadatas, ids)`
- Metadata per chunk: `{source_file, chunk_index, effective_date (if parseable from filename)}`
- Idempotent — check if collection already has documents before re-ingesting
- One-time CLI entry point: `python -m banking_agents.rag.policy.ingest` and `python -m banking_agents.rag.loan.ingest`

**Loan vs Policy split:**
- Policy ingest: all 25 docs in `Policy docs for RAG/` → `policy_docs` ChromaDB collection
- Loan ingest: filter to loan-related docs (files 09–18) → `loan_docs` collection (or ingest all with metadata tag and filter at query time)

---

### 1.6 RAG Query Wrappers — `rag/policy/query.py` and `rag/loan/query.py`

**What to implement:**
- `PolicyQueryEngine` and `LoanQueryEngine` classes
- Each wraps `BaseRAG.retrieve()` and adds:
  - Similarity score filtering (threshold-based, see constraints section)
  - Result formatting with source citations
  - Staleness check on `effective_date` metadata field
- Domain agents use these instead of calling `BaseRAG` directly

---

### 1.7 RAG Retriever — `rag/retriever.py`

Currently empty alongside `base_rag.py` which does the same job.

**What to implement:**
- Either extend `BaseRAG` with the filtering/scoring logic here, or keep `retriever.py` as a thin facade and delete the duplication
- Recommended: move all retrieval logic here, make `BaseRAG` just the ChromaDB + embedding init, and have `retriever.py` own `retrieve_with_scores()` and `retrieve_filtered()`

---

### 1.8 Agent Context — `context/agent_context.py`

Currently `AgentContext` is defined in `communication/message.py`. The `context/agent_context.py` file is empty.

**What to implement:**
- Move `AgentContext` definition here (it's the right home)
- Add `per_query_token_count: int = 0` and `per_query_tool_calls: int = 0` fields (needed for constraint tracking)
- Add `escalation_flags: list[str] = []` for audit trail
- Update imports in `message.py` and `app.py`

---

### 1.9 Observability — `observability/logger.py` and `observability/tracer.py`

**`logger.py`:**
- Structured JSON logger wrapping Python's `logging` module
- Fields on every log entry: `timestamp`, `session_id`, `agent_name`, `event_type`, `duration_ms`, `model_id`, `input_tokens`, `output_tokens`
- Log levels: `INFO` for normal hops, `WARN` for escalations and constraint hits, `ERROR` for failures
- Usage: `logger.log_agent_call(agent="PolicyRAGAgent", session_id=..., ...)`

**`tracer.py`:**
- Lightweight call-chain tracer — records the sequence of agents/tools invoked per query
- `Tracer.start_trace(session_id, query)` → returns `trace_id`
- `Tracer.add_hop(trace_id, agent, input_summary, output_summary, duration_ms)`
- `Tracer.end_trace(trace_id)` → returns full trace as dict (logged or stored)
- Enables post-hoc debugging of "why did the orchestrator loop X times?"

---

## Track 2: Constraints Handling and Guardrails

### Architecture

All guardrails are implemented as a layered pipeline. The request passes through each layer sequentially. Any layer can reject the request early with a typed error.

```
HTTP Request
    └── [Layer 1] InputValidator          ← structural + content checks
    └── [Layer 2] IntentGuard             ← post-classification safety
    └── [Layer 3] OrchestratorConstraints ← loop + cost + timeout limits
    └── [Layer 4] AgentGuards             ← per-agent RAG + rule checks
    └── [Layer 5] OutputValidator         ← response safety + format
    └── HTTP Response
```

A new module `guardrails/` holds all implementations.

---

### 2.1 Input Validation — `guardrails/input_validator.py`

**Class:** `InputValidator`

**Checks (in order):**

| Check | Rule | Action on fail |
|---|---|---|
| Query length | 10 ≤ len(query) ≤ 2000 chars | Return 400 with "Query too short/long" |
| Encoding | Valid UTF-8, no null bytes | Return 400 |
| Prompt injection | Regex patterns: "ignore previous", "system prompt", "jailbreak", "act as", "DAN" | Return 400 with generic refusal |
| Gibberish filter | Ratio of non-alpha chars > 0.7 in a 20+ char query | Return 400 |
| PII scrubbing | Detect and mask: card numbers (Luhn), 12-digit Aadhaar, 10-digit PAN, account number patterns | Scrub in-place, log detection event, continue |

**Where it runs:** FastAPI middleware, before the request reaches the Orchestrator.

**Config (`config/guardrails.yaml`):**
```yaml
input:
  min_query_length: 10
  max_query_length: 2000
  injection_patterns:
    - "ignore previous instructions"
    - "you are now"
    - "act as"
    - "jailbreak"
  pii_patterns:
    card_number: '\b(?:\d[ -]?){13,16}\b'
    aadhaar: '\b\d{4}\s\d{4}\s\d{4}\b'
    pan: '\b[A-Z]{5}\d{4}[A-Z]\b'
```

---

### 2.2 Intent-Level Guard — `guardrails/intent_guard.py`

**Class:** `IntentGuard`

Runs after `IntentClassifierAgent` returns, before `TaskDecomposerAgent` runs.

**Checks:**

| Condition | Action |
|---|---|
| `confidence < 0.5` | Return "Could you clarify your question?" — don't proceed |
| `intent == UNKNOWN` | Return canned out-of-scope response, no LLM calls downstream |
| `intent == FRAUD_ALERT` | (excluded from scope — handled by separate flow) |
| Query length > 500 chars AND confidence < 0.7 | Force clarification before decomposition |

**Config (`config/guardrails.yaml`):**
```yaml
intent:
  min_confidence_threshold: 0.5
  clarification_threshold: 0.7
  clarification_length_trigger: 500
```

---

### 2.3 Orchestrator Execution Constraints — `guardrails/orchestrator_constraints.py`

**Class:** `OrchestratorConstraints`

Enforced inside the Orchestrator's `while True` tool-calling loop.

**Constraints:**

| Constraint | Limit | Action on breach |
|---|---|---|
| Max tool-call iterations | 6 per query | Break loop, return partial response with warning |
| Cycle detection | Same tool called with same input twice | Break loop immediately, log warning |
| Per-query token budget | 8000 input tokens total across all hops | Abort, return "Query too complex" |
| Per-hop timeout | 15 seconds per Bedrock call | Raise timeout, trigger fallback |
| Max subtasks from TaskDecomposer | 4 subtasks | Truncate list to 4, log warning |

**Implementation:**
- `OrchestratorConstraints` wraps the loop state: `iteration_count`, `tool_call_log: list[(tool_name, input_hash)]`, `total_tokens_used`
- Orchestrator calls `constraints.check_before_hop()` at the top of each loop iteration
- Token counts read from Bedrock response's `usage` field (already returned by `converse()`)

**Config (`config/guardrails.yaml`):**
```yaml
orchestrator:
  max_iterations: 6
  max_subtasks: 4
  max_input_tokens_per_query: 8000
  per_hop_timeout_seconds: 15
  token_budget_action: "abort"  # or "warn"
```

---

### 2.4 RAG Confidence Gate — `guardrails/rag_guard.py`

**Class:** `RAGGuard`

Runs inside `PolicyQueryEngine` and `LoanQueryEngine` after retrieval, before generation.

**Checks:**

| Condition | Action |
|---|---|
| All retrieved chunks have distance > threshold (low similarity) | Don't call LLM. Return "I don't have enough information in the policy documents to answer this." |
| Best chunk distance > soft threshold | Generate answer but append disclaimer: "This answer is based on partial matches. Please verify with a bank representative." |
| Retrieved chunk `effective_date` is older than 1 year | Append staleness warning to response |
| Zero documents retrieved | Return "No relevant policy found." immediately |

**Config (`config/guardrails.yaml`):**
```yaml
rag:
  policy:
    hard_distance_threshold: 1.2    # ChromaDB L2 distance — above this = no answer
    soft_distance_threshold: 0.9    # Above this = answer with disclaimer
    max_chunk_age_days: 365
    n_results: 3
  loan:
    hard_distance_threshold: 1.2
    soft_distance_threshold: 0.9
    max_chunk_age_days: 365
    n_results: 4
```

---

### 2.5 Loan Eligibility Hard Rules — `guardrails/eligibility_guard.py`

**Class:** `EligibilityGuard`

Wraps `EligibilityChecker` (from 1.4). Enforces that LLM reasoning never overrides deterministic rule outcomes.

**Flow:**
1. `LoanEligibilityRAGAgent.answer(task)` first extracts applicant parameters from the query text using a small LLM call (Haiku)
2. `EligibilityGuard.evaluate(extracted_params, loan_type)` runs deterministic checks
3. Result: `{eligible, passed_rules, failed_rules}`
4. LLM is called only to generate a human-readable explanation of the deterministic result
5. Output is post-processed: if LLM says "eligible" but `EligibilityGuard` says `eligible=False`, the LLM response is discarded and the deterministic result is used

**Numeric bounds validation (before rule evaluation):**
- Income: must be > 0 and < 10,000,000
- CIBIL score: must be between 300 and 900
- Age: must be between 18 and 100
- Loan amount: must be > 0
- Any out-of-bounds value → return "Invalid applicant data, please re-enter."

---

### 2.6 Output Guardrails — `guardrails/output_validator.py`

**Class:** `OutputValidator`

Runs on every agent response before it reaches the user.

**Checks:**

| Check | Rule | Action |
|---|---|---|
| Empty response | Response is blank or whitespace | Trigger one retry; if still empty, return fallback message |
| Response length | > 3000 characters | Truncate at last complete sentence before limit, append "…" |
| PII leak detection | Same regex patterns as input validator | Redact matches before returning |
| Internal detail exposure | Patterns: "traceback", "boto3", "chromadb", "Exception", AWS ARN pattern | Strip matched lines from response |
| Hallucination signal | Response contains "I know that" or "Generally speaking" without citing a document | Append disclaimer |
| Confidence disclaimer injection | `intent == LOAN_ELIGIBILITY` | Always append: "This assessment is indicative. Final eligibility is subject to bank verification." |

---

### 2.7 Session & Rate Constraints — `guardrails/session_guard.py`

**Class:** `SessionGuard`

Enforced in the FastAPI endpoint before calling the Orchestrator.

**Constraints:**

| Constraint | Limit | Action |
|---|---|---|
| Requests per session per minute | 10 | Return 429 |
| Max session context history | 20 turns | Evict oldest turn before adding new one |
| Session TTL | 30 minutes of inactivity | Expire session, user gets a fresh context |
| Duplicate query detection | Same query string in last 3 turns of session | Return cached previous response without new LLM calls |

**Config (`config/guardrails.yaml`):**
```yaml
session:
  max_requests_per_minute: 10
  max_history_turns: 20
  inactivity_ttl_minutes: 30
  dedup_window_turns: 3
```

---

### 2.8 Guardrails Config File — `config/guardrails.yaml`

Single source of truth for all thresholds. All guard classes read from this at init. Allows tuning without code changes.

Full structure combines all `config` blocks shown in sections 2.1–2.7 above into one file.

---

## File Checklist

| File | Status | Track |
|---|---|---|
| `agents/base.py` | Implement | 1.1 |
| `tools/registry.py` | Implement | 1.2 |
| `tools/document_search.py` | Implement | 1.3 |
| `tools/eligibility_checker.py` | Implement | 1.4 |
| `config/eligibility_rules.yaml` | Create | 1.4 |
| `rag/policy/ingest.py` | Implement | 1.5 |
| `rag/loan/ingest.py` | Implement | 1.5 |
| `rag/policy/query.py` | Implement | 1.6 |
| `rag/loan/query.py` | Implement | 1.6 |
| `rag/retriever.py` | Implement | 1.7 |
| `context/agent_context.py` | Implement | 1.8 |
| `observability/logger.py` | Implement | 1.9 |
| `observability/tracer.py` | Implement | 1.9 |
| `guardrails/__init__.py` | Create | 2 |
| `guardrails/input_validator.py` | Create | 2.1 |
| `guardrails/intent_guard.py` | Create | 2.2 |
| `guardrails/orchestrator_constraints.py` | Create | 2.3 |
| `guardrails/rag_guard.py` | Create | 2.4 |
| `guardrails/eligibility_guard.py` | Create | 2.5 |
| `guardrails/output_validator.py` | Create | 2.6 |
| `guardrails/session_guard.py` | Create | 2.7 |
| `config/guardrails.yaml` | Create | 2.8 |

---

## Integration Points

### Where guards plug into existing code

**`app.py`:**
- Add `SessionGuard` call before `orchestrator.run()`
- Add `InputValidator` call before session lookup
- Add `OutputValidator` call on `agent_response.response` before building `ChatResponse`

**`agents/reusable/orchestrator.py`:**
- Instantiate `OrchestratorConstraints` at the start of `run()`
- Call `constraints.check_before_hop()` at the top of the `while True` loop
- Pass `IntentGuard` check result after `classify_intent` tool call returns

**`agents/domain/policy_rag_agent.py`:**
- Replace direct `BaseRAG` usage with `PolicyQueryEngine` from `rag/policy/query.py`
- `PolicyQueryEngine` internally applies `RAGGuard` before returning results

**`agents/domain/loan_eligibility_rag_agent.py`:**
- Call `EligibilityGuard.evaluate()` before LLM generation step
- Pass deterministic result to LLM as context, not as a question to answer

---

## Recommended Implementation Order

1. `agents/base.py` — unblocks all agent work
2. `rag/policy/ingest.py` + `rag/loan/ingest.py` — run ingest immediately to populate ChromaDB; nothing works without data
3. `rag/retriever.py` + `rag/policy/query.py` + `rag/loan/query.py` — makes RAG functional end-to-end
4. `tools/registry.py` — clean up Orchestrator, then update domain agents to use `DocumentSearchTool`
5. `tools/eligibility_checker.py` + `config/eligibility_rules.yaml` — deterministic loan rules
6. `context/agent_context.py` — needed before adding constraint tracking fields
7. `guardrails/` (all files) + `config/guardrails.yaml` — add all guards
8. `observability/logger.py` + `observability/tracer.py` — wire in last, after the core pipeline is stable
