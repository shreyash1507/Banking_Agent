import os
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Centralized Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.info("Settings module loaded. Logging initialized.")

# ---------------------------------------------------------------------------
# Groq Model IDs
# Docs: https://console.groq.com/docs/models
# ---------------------------------------------------------------------------
MODEL_INTENT_CLASSIFIER   = "llama-3.1-8b-instant"      # Fast — classification only
MODEL_TASK_DECOMPOSER     = "llama-3.1-8b-instant"      # Fast — structured JSON output
MODEL_ORCHESTRATOR        = "llama-3.3-70b-versatile"   # Powerful — tool use + reasoning
MODEL_POLICY_RAG_DEFAULT  = "llama-3.1-8b-instant"      # Fast RAG answer generation
MODEL_POLICY_RAG_FALLBACK = "llama-3.3-70b-versatile"   # Fallback for complex queries
MODEL_LOAN_ELIGIBILITY    = "llama-3.3-70b-versatile"   # Strict numerical reasoning

def get_groq_client() -> Groq:
    """Initializes and returns a Groq client with max 1 retry to preserve rate limits."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in environment variables.")
    return Groq(api_key=api_key, max_retries=1)
