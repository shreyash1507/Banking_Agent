# Problem Statement


Banks today handle a large volume of customer queries related to policies, loans, KYC, disputes, compliance, account services, and regulatory procedures. Traditional chatbots often fail to understand complex requests, manage multilingual conversations, detect urgency, or provide contextual and accurate policy guidance. These limitations lead to poor customer experience, delayed resolutions, and increased dependency on human support teams.

To address this challenge, we propose an Agentic Policy Bot Navigator — a multi-agent AI system designed specifically for banking customers. The solution leverages autonomous and collaborative AI agents to intelligently understand, decompose, process, and resolve customer policy-related queries in real time.

The primary focus of this project is to build an agentic AI architecture where multiple intelligent agents work collaboratively to deliver accurate, contextual, scalable, and customer-centric banking policy assistance while improving operational efficiency and customer satisfaction.

# Development Goal: 
Showcase the Reusability of Agents Using 2 Use cases: 1- Policy Document Bot 2- Loan Eligibility Bot
Reusable/Configurable Agents:
- IntentClassifierAgent (reusable)
- TaskDecomposerAgent (reusable)
- OrchestratorAgent (reusable)

Domain-Specific Agents:
- PolicyRAGAgent
- LoanEligibilityRAGAgent 

Agents Flow-> 
User Query
  └── OrchestratorAgent
        └── IntentClassifierAgent       → Intent: POLICY | LOAN_ELIGIBILITY | UNKNOWN
              └── TaskDecomposerAgent   → [subtask_1, subtask_2, ...]
                    ├── PolicyRAGAgent          (if POLICY intent)
                    └── LoanEligibilityRAGAgent (if LOAN_ELIGIBILITY intent)

RAG for Agents

Backend API
- Python FastAPI
- API for Policy Document Bot
- API for Loan Eligibility Bot

Frontend- 
Next.js + Tailwind CSS 

