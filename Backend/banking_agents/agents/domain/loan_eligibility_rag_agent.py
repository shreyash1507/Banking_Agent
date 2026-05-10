import logging
from groq import Groq
from banking_agents.config.settings import get_groq_client, MODEL_LOAN_ELIGIBILITY
from banking_agents.rag.base_rag import BaseRAG

logger = logging.getLogger(__name__)


class LoanEligibilityRAGAgent:
    def __init__(self):
        logger.info("[LoanEligibilityRAGAgent] Initializing LoanEligibilityRAGAgent.")
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_LOAN_ELIGIBILITY
        logger.debug("[LoanEligibilityRAGAgent] Using model: %s", self.model_id)
        self.rag = BaseRAG(collection_name="loan_docs")
        logger.info("[LoanEligibilityRAGAgent] Initialized with RAG collection: 'loan_docs'")

    def answer(self, task: str) -> str:
        """Retrieves relevant loan eligibility documents and generates an answer."""
        logger.info("[LoanEligibilityRAGAgent.answer] >>> Task: '%s'", task)

        logger.debug("[LoanEligibilityRAGAgent.answer] Retrieving loan documents from ChromaDB...")
        retrieved_docs = self.rag.retrieve(task, n_results=4)
        logger.info("[LoanEligibilityRAGAgent.answer] Retrieved %d document(s).", len(retrieved_docs))
        context_text = "\n\n".join([doc["content"] for doc in retrieved_docs])

        system_prompt = """You are an expert Loan Eligibility Assessor for the bank.
Use the provided loan guidelines to answer the user's eligibility question.
Pay very close attention to numerical thresholds (income, CIBIL scores, tenure limits, margins).
Perform step-by-step mathematical reasoning if required to determine eligibility.
If there are multiple criteria, explicitly list which are met and which are not.
Do not guess or assume. If information is incomplete, explain what is missing."""

        user_message = f"Loan Guidelines Context:\n{context_text}\n\nUser Question: {task}"

        try:
            logger.debug("[LoanEligibilityRAGAgent.answer] Calling Groq API | Model: %s", self.model_id)
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                temperature=0.0,  # Zero temperature for strict rule evaluation
            )
            result = response.choices[0].message.content.strip()
            logger.info("[LoanEligibilityRAGAgent.answer] <<< Response received (%d chars).", len(result))
            return result

        except Exception as e:
            logger.error("[LoanEligibilityRAGAgent.answer] Error: %s", e, exc_info=True)
            return "I apologize, but I encountered an error while assessing loan eligibility."
