import json
import logging
from groq import Groq
from banking_agents.config.settings import get_groq_client, MODEL_TASK_DECOMPOSER

logger = logging.getLogger(__name__)

class TaskDecomposerAgent:
    def __init__(self):
        logger.info("[TaskDecomposerAgent] Initializing TaskDecomposerAgent.")
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_TASK_DECOMPOSER
        logger.debug("[TaskDecomposerAgent] Using model: %s", self.model_id)

    def decompose(self, query: str, intent: str) -> list[str]:
        """Decomposes a complex user query into a list of actionable sub-tasks."""
        logger.info("[TaskDecomposerAgent.decompose] >>> Query: '%s' | Intent: '%s'", query, intent)

        system_prompt = f"""You are an expert banking task decomposer.
The user has asked a query classified as: {intent}.
Break this query into a logical sequence of atomic sub-tasks for domain agents to answer.

Return ONLY a JSON array of strings. No markdown, no extra text.
Example: ["What is the current auto loan interest rate?", "What is the minimum credit score required?"]"""

        try:
            logger.debug("[TaskDecomposerAgent.decompose] Calling Groq API | Model: %s", self.model_id)
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": query},
                ],
                temperature=0.2,
            )
            output_text = response.choices[0].message.content.strip()
            logger.debug("[TaskDecomposerAgent.decompose] Raw response: %s", output_text)

            # Strip markdown code fences if present
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            if output_text.startswith("```"):
                output_text = output_text[3:]
            if output_text.endswith("```"):
                output_text = output_text[:-3]

            tasks = json.loads(output_text.strip())
            if isinstance(tasks, list):
                logger.info("[TaskDecomposerAgent.decompose] <<< Decomposed into %d subtask(s): %s", len(tasks), tasks)
                return tasks

            logger.warning("[TaskDecomposerAgent.decompose] Unexpected format, falling back to single task.")
            return [query]

        except Exception as e:
            logger.error("[TaskDecomposerAgent.decompose] Error: %s", e, exc_info=True)
            return [query]
