import logging

logger = logging.getLogger(__name__)

class RAGGuard:
    """
    Prevents hallucination by checking the relevance distance of retrieved documents.
    ChromaDB returns L2 distance (lower is better).
    """
    def __init__(self, config: dict):
        self.hard_threshold = config.get("hard_distance_threshold", 1.2)
        self.soft_threshold = config.get("soft_distance_threshold", 0.9)
        self.no_result_message = config.get("no_result_message", "No relevant information found.")
        self.disclaimer = config.get("low_confidence_disclaimer", "Disclaimer: Partial match.")

    def check(self, retrieved_results: dict) -> tuple[bool, str | None]:
        """
        Analyzes retrieval results and decides whether to proceed.
        Returns: (proceed_with_llm, message_or_disclaimer)
        """
        # If no documents retrieved at all
        if not retrieved_results or not retrieved_results.get("documents") or not retrieved_results["documents"][0]:
            logger.warning("[RAGGuard] No documents retrieved.")
            return False, self.no_result_message

        # Distances are in a list of lists: [[d1, d2, ...]]
        distances = retrieved_results.get("distances", [[]])[0]
        if not distances:
            logger.warning("[RAGGuard] No distances found in results.")
            return False, self.no_result_message

        min_dist = min(distances)
        logger.info("[RAGGuard] Minimum retrieval distance: %.4f", min_dist)

        # 1. Above hard threshold -> irrelevant
        if min_dist > self.hard_threshold:
            logger.warning("[RAGGuard] Distance %.4f exceeds hard threshold %.4f", min_dist, self.hard_threshold)
            return False, self.no_result_message

        # 2. Between soft and hard threshold -> weak match
        if min_dist > self.soft_threshold:
            logger.info("[RAGGuard] Distance %.4f is between soft and hard threshold. Adding disclaimer.", min_dist)
            return True, self.disclaimer

        # 3. Below soft threshold -> strong match
        return True, None
