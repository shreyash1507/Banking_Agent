# Implementation Plan: YAML-Configurable Agents

## Goal
Transform the hardcoded reusable agents (`IntentClassifier` and `Orchestrator`) into fully dynamic, configuration-driven components. By moving the intent definitions and tool mappings into an `agents.yaml` file, you will be able to expand the bot's capabilities (adding new intents or domain experts) without modifying the core Python routing logic.

## Proposed Changes

### 1. Dependencies
- Add `PyYAML` to `pyproject.toml` and `requirements.txt`.

### 2. The Configuration Schema (`config/agents.yaml`)
We will create a YAML file that acts as the single source of truth for the system's capabilities.
```yaml
intents:
  POLICY: "Queries related to banking rules, terms and conditions, fees, and general policies."
  LOAN_ELIGIBILITY: "Queries specifically about checking if the user is eligible for a loan, loan rates, or loan conditions."
  UNKNOWN: "Greetings, small talk, or queries completely unrelated to banking."

tools:
  - name: consult_policy_expert
    description: Queries the policy database to answer rules/terms related questions.
    input_property: task
    module_path: banking_agents.agents.domain.policy_rag_agent
    class_name: PolicyRAGAgent
  
  - name: consult_loan_expert
    description: Queries the loan guidelines to answer eligibility and numeric loan questions.
    input_property: task
    module_path: banking_agents.agents.domain.loan_eligibility_rag_agent
    class_name: LoanEligibilityRAGAgent
```

### 3. Dynamic Tool Registry (`tools/registry.py`)
Currently, the Orchestrator has a massive block of hardcoded AWS Bedrock tool schemas and a hardcoded `if/elif` block to route tool calls. 
- We will build a `ToolRegistry` class that reads the `agents.yaml` file.
- **Dynamic Loading:** It will use Python's `importlib` to automatically load and instantiate `PolicyRAGAgent`, `LoanEligibilityRAGAgent`, or any future agents based purely on the YAML `module_path`.
- **Dynamic Schema Generation:** It will automatically construct the Bedrock `toolConfig` schema based on the YAML entries.

### 4. Refactoring `IntentClassifierAgent`
- Remove the hardcoded classification categories from the system prompt.
- Read the `intents` section from `agents.yaml` and inject it into the prompt. If you add a "CREDIT_CARD_SUPPORT" intent to the YAML, the prompt will automatically instruct Nova Micro to classify it.

### 5. Refactoring `OrchestratorAgent`
- Remove all `import PolicyRAGAgent` and `import LoanEligibilityRAGAgent` statements.
- The Orchestrator will query the `ToolRegistry` for its available tools and pass the execution to the registry when Bedrock requests a tool call.

---

## Verification Plan
1. Refactor the code.
2. Run a query that triggers the `PolicyRAGAgent`.
3. The system should successfully route the query to the dynamically loaded Python class purely based on the YAML mapping.
