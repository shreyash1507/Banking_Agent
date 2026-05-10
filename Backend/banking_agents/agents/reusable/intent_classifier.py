import json
import logging
from groq import Groq
from banking_agents.config.settings import get_groq_client, MODEL_INTENT_CLASSIFIER

logger = logging.getLogger(__name__)

class IntentClassifierAgent:
    def __init__(self, intents: list[dict]):
        logger.info("[IntentClassifierAgent] Initializing with %d intent(s).", len(intents))
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_INTENT_CLASSIFIER
        self.intents = intents
        logger.debug("[IntentClassifierAgent] Using model: %s", self.model_id)

    def _build_system_prompt(self) -> str:
        intent_list = "\n".join(
            f"- {i['name']}: {i['description']}" for i in self.intents
        )
        return f"""You are an expert banking intent classifier.
Classify the user's intent into exactly one of the following categories:
{intent_list}
- UNKNOWN: Greetings, small talk, or queries completely unrelated to banking.

Return ONLY a raw JSON object with two keys: "intent" (string) and "confidence" (float between 0 and 1). Do not use markdown blocks."""

    def classify(self, query: str) -> dict:
        logger.info("[IntentClassifierAgent.classify] >>> Classifying query: '%s'", query)
        try:
            logger.debug("[IntentClassifierAgent.classify] Calling Groq API | Model: %s", self.model_id)
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user",   "content": query},
                ],
                temperature=0.0,
            )
            output_text = response.choices[0].message.content.strip()
            logger.debug("[IntentClassifierAgent.classify] Raw response: %s", output_text)

            # Strip markdown code fences if present
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            if output_text.startswith("```"):
                output_text = output_text[3:]
            if output_text.endswith("```"):
                output_text = output_text[:-3]

            result = json.loads(output_text.strip())
            logger.info("[IntentClassifierAgent.classify] <<< Result: intent='%s', confidence=%.2f",
                        result.get("intent"), result.get("confidence"))
            return result
        except Exception as e:
            logger.error("[IntentClassifierAgent.classify] Error: %s", e, exc_info=True)
            return {"intent": "UNKNOWN", "confidence": 0.0}
