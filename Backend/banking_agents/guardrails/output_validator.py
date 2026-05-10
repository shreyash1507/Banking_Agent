import logging

logger = logging.getLogger(__name__)

class OutputValidator:
    """
    Validates and enriches the final agent output.
    """
    def __init__(self, config: dict):
        self.fallback = config.get("empty_response_fallback", "I'm sorry, I couldn't generate a response.")
        self.intent_disclaimers = config.get("intent_disclaimers", {})

    def validate(self, response: str, intent: str | None = None) -> str:
        """
        Ensures response is not empty and appends intent-specific disclaimers.
        """
        if not response or not response.strip():
            logger.warning("[OutputValidator] Empty response detected. Using fallback.")
            return self.fallback

        # Append disclaimer if intent matches
        if intent and intent in self.intent_disclaimers:
            disclaimer = self.intent_disclaimers[intent]
            logger.info("[OutputValidator] Appending disclaimer for intent: %s", intent)
            # Avoid duplicate disclaimer if already present
            if disclaimer not in response:
                response = f"{response.strip()}\n\n{disclaimer}"

        return response
