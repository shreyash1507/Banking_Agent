import logging
import json
from groq import Groq
from banking_agents.config.settings import get_groq_client, MODEL_POLICY_RAG_DEFAULT, MODEL_POLICY_RAG_FALLBACK
from banking_agents.rag.base_rag import BaseRAG
from banking_agents.guardrails.rag_guard import RAGGuard

logger = logging.getLogger(__name__)


class PolicyRAGAgent:
    def __init__(self, guardrails_config: dict = None):
        logger.info("[PolicyRAGAgent] Initializing PolicyRAGAgent.")
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_POLICY_RAG_DEFAULT
        self.fallback_model_id = MODEL_POLICY_RAG_FALLBACK
        logger.debug("[PolicyRAGAgent] Primary model: %s | Fallback: %s", self.model_id, self.fallback_model_id)
        self.rag = BaseRAG(collection_name="policy_docs")
        
        # Guardrails
        if guardrails_config and "rag" in guardrails_config:
            self.rag_guard = RAGGuard(guardrails_config["rag"])
        else:
            self.rag_guard = None
            
        logger.info("[PolicyRAGAgent] Initialized with RAG collection: 'policy_docs'")

    def answer(self, task: str) -> str:
        """Retrieves relevant policy documents and generates an answer."""
        logger.info("[PolicyRAGAgent.answer] >>> Task: '%s'", task)

        logger.debug("[PolicyRAGAgent.answer] Retrieving policy documents from ChromaDB...")
        # Get raw results to pass to RAGGuard (includes distances)
        retrieved_results = self.rag.collection.query(
            query_texts=[task],
            n_results=3,
        )
        
        disclaimer = None
        if self.rag_guard:
            proceed, message = self.rag_guard.check(retrieved_results)
            if not proceed:
                logger.warning("[PolicyRAGAgent.answer] RAGGuard blocked the query: %s", message)
                return message
            disclaimer = message # Store disclaimer to append later if it exists

        # Convert to list of dicts for backward compatibility in this method if needed, 
        # but here we just need the content.
        documents = retrieved_results.get("documents", [[]])[0]
        context_text = "\n\n".join(documents)
        logger.info("[PolicyRAGAgent.answer] Retrieved %d document(s).", len(documents))

        system_prompt = """You are a bank policy expert.
Use the provided policy documents to answer the user's question accurately.
If the answer is not contained within the documents, state that clearly.
Do not make up policies or information. Provide precise answers."""

        user_message = f"Policy Documents Context:\n{context_text}\n\nUser Question: {task}"

        try:
            logger.debug("[PolicyRAGAgent.answer] Calling Groq API | Model: %s", self.model_id)
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                temperature=0.1,
            )
            output_text = response.choices[0].message.content.strip()
            logger.debug("[PolicyRAGAgent.answer] Primary model response (preview): %s...", output_text[:200])

            # Escalate to fallback model if low confidence is expressed
            if "I'm not completely sure" in output_text or "does not clearly state" in output_text:
                logger.warning("[PolicyRAGAgent.answer] Low confidence detected. Escalating to fallback: %s", self.fallback_model_id)
                fallback_response = self.client.chat.completions.create(
                    model=self.fallback_model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_message},
                    ],
                    temperature=0.1,
                )
                fallback_text = fallback_response.choices[0].message.content.strip()
                logger.info("[PolicyRAGAgent.answer] <<< Returning fallback model response.")
                return fallback_text

            logger.info("[PolicyRAGAgent.answer] <<< Returning primary model response.")
            if disclaimer:
                output_text += f"\n\n{disclaimer}"
            return output_text

        except Exception as e:
            logger.error("[PolicyRAGAgent.answer] Error: %s", e, exc_info=True)
            return "I apologize, but I encountered an error while retrieving the policy information."
