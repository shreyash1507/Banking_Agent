import logging
import math
from groq import Groq
from typing import Optional
from banking_agents.config.settings import get_groq_client, MODEL_LOAN_ELIGIBILITY
from banking_agents.rag.base_rag import BaseRAG
from banking_agents.guardrails.rag_guard import RAGGuard
from banking_agents.communication.message import CustomerLoanProfile

logger = logging.getLogger(__name__)


class LoanEligibilityRAGAgent:
    def __init__(self, guardrails_config: dict = None):
        logger.info("[LoanEligibilityRAGAgent] Initializing LoanEligibilityRAGAgent.")
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_LOAN_ELIGIBILITY
        logger.debug("[LoanEligibilityRAGAgent] Using model: %s", self.model_id)
        self.rag = BaseRAG(collection_name="loan_docs")

        # Guardrails
        if guardrails_config and "rag" in guardrails_config:
            self.rag_guard = RAGGuard(guardrails_config["rag"])
        else:
            self.rag_guard = None

        logger.info("[LoanEligibilityRAGAgent] Initialized with RAG collection: 'loan_docs'")

    # ------------------------------------------------------------------
    # Core entry point — handles both structured and freeform input
    # ------------------------------------------------------------------
    def answer(self, task: str, loan_profile: Optional[CustomerLoanProfile] = None) -> str:
        """
        Assess loan eligibility.
        - If loan_profile is provided: computes derived metrics from the profile
          and asks the LLM to validate them against the retrieved policy thresholds.
        - If loan_profile is None: falls back to freeform RAG-based assessment.
        """
        logger.info("[LoanEligibilityRAGAgent.answer] >>> Task: '%s'", task)

        # Retrieve relevant loan policy documents - INCREASED n_results for decision matrices
        retrieved_results = self.rag.collection.query(query_texts=[task], n_results=8)

        disclaimer = None
        if self.rag_guard:
            proceed, message = self.rag_guard.check(retrieved_results)
            if not proceed:
                logger.warning("[LoanEligibilityRAGAgent.answer] RAGGuard blocked: %s", message)
                return message
            disclaimer = message

        documents = retrieved_results.get("documents", [[]])[0]
        context_text = "\n\n".join(documents)
        logger.info("[LoanEligibilityRAGAgent.answer] Retrieved %d document(s).", len(documents))

        if loan_profile:
            return self._assess_with_profile(task, loan_profile, context_text, disclaimer)
        else:
            return self._assess_freeform(task, context_text, disclaimer)

    # ------------------------------------------------------------------
    # Structured path — implements the 4-stage reasoning protocol
    # ------------------------------------------------------------------
    def _assess_with_profile(
        self, task: str, p: CustomerLoanProfile, context_text: str, disclaimer: Optional[str]
    ) -> str:
        logger.info("[LoanEligibilityRAGAgent] Running structured assessment for %s loan.", p.loan_type)

        # Pre-compute metrics as inputs for LLM validation
        if p.loan_tenure_months > 0:
            monthly_rate = 0.01  # placeholder rate for order-of-magnitude estimation
            proposed_emi = (p.loan_amount_requested * monthly_rate) / (
                1 - math.pow(1 + monthly_rate, -p.loan_tenure_months)
            )
        else:
            proposed_emi = 0.0

        total_obligations    = p.existing_emi_amount + proposed_emi
        foir                 = total_obligations / p.monthly_income if p.monthly_income > 0 else None
        ltv                  = (p.loan_amount_requested / p.property_value) if p.property_value else None
        age_at_maturity      = p.applicant_age + (p.loan_tenure_months / 12)

        derived_metrics = f"""
=== APPLICANT PROFILE ===
Loan Type:                  {p.loan_type}
Employment Type:            {p.employment_type}
Applicant Age:              {p.applicant_age} years
Monthly Income:             ₹{p.monthly_income:,.2f}
Existing Monthly EMI:       ₹{p.existing_emi_amount:,.2f}
Requested Loan Amount:      ₹{p.loan_amount_requested:,.2f}
Requested Tenure:           {p.loan_tenure_months} months
CIBIL Score:                {p.cibil_score}
Property / Asset Value:     {"₹{:,.2f}".format(p.property_value) if p.property_value else "Not Provided"}

=== DERIVED CALCULATIONS ===
Approximate Proposed EMI:   ₹{proposed_emi:,.2f}/month
Total EMI Obligations:      ₹{total_obligations:,.2f}/month
FOIR:                       {f"{foir:.2%}" if foir is not None else "N/A"}
LTV Ratio:                  {f"{ltv:.2%}" if ltv is not None else "N/A"}
Age at Loan Maturity:       {age_at_maturity:.1f} years
=========================================
"""

        system_prompt = """You are an expert Loan Eligibility Assessor.
You must follow this strictly prioritized 4-stage reasoning protocol:

1. DIRECT SCENARIO MATCH: Check if the policy text contains a specific clause for this exact loan type and applicant profile.
2. CATEGORICAL RULE SCAN: Look for decision matrices, score bands, and hard cutoffs (e.g., "Score < 700 = Decline"). If a "Hard No" or "Hard Limit" is found, stop and report the rejection reason. Hard rules override all calculations.
3. FORMULA EXTRACTION: If categorical rules are passed, extract the mathematical formulas (FOIR, LTV, EMI multipliers) from the policy.
4. INTEGRATED CALCULATION: Apply the extracted formulas to the derived metrics to reach a final assessment.

If no exact rule is found for a value, state "No specific threshold found in policy" and provide a best-effort assessment based on general banking principles mentioned elsewhere in the text.

Show your reasoning for each stage clearly."""

        user_message = (
            f"=== OFFICIAL BANK LOAN POLICY GUIDELINES ===\n{context_text}\n\n"
            f"{derived_metrics}\n"
            f"Original Question: {task}\n\n"
            "Provide a structured assessment following the 4-stage protocol."
        )

        return self._call_llm(system_prompt, user_message, disclaimer)

    # ------------------------------------------------------------------
    # Freeform fallback path
    # ------------------------------------------------------------------
    def _assess_freeform(self, task: str, context_text: str, disclaimer: Optional[str]) -> str:
        logger.info("[LoanEligibilityRAGAgent] Running freeform assessment.")

        system_prompt = """You are an expert Loan Eligibility Assessor.
Use the 4-stage reasoning protocol:
1. Scenario Match
2. Categorical Rule/Threshold Lookup (Decisions tables/matrices/cutoffs)
3. Formula Extraction
4. Calculation

Categorical rules (e.g., CIBIL minimums) take priority over formulas. If a value falls into an 'Ineligible' band, state it clearly.
If data is missing, ask for it."""

        user_message = (
            f"=== OFFICIAL BANK LOAN POLICY GUIDELINES ===\n{context_text}\n\n"
            f"User Question: {task}"
        )
        return self._call_llm(system_prompt, user_message, disclaimer)

    # ------------------------------------------------------------------
    # Shared LLM call
    # ------------------------------------------------------------------
    def _call_llm(self, system_prompt: str, user_message: str, disclaimer: Optional[str]) -> str:
        try:
            logger.debug("[LoanEligibilityRAGAgent] Calling Groq API | Model: %s", self.model_id)
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                temperature=0.0,  # Zero temperature for strict rule evaluation
            )
            result = response.choices[0].message.content.strip()
            logger.info("[LoanEligibilityRAGAgent] <<< Response received (%d chars).", len(result))
            if disclaimer:
                result += f"\n\n{disclaimer}"
            return result

        except Exception as e:
            logger.error("[LoanEligibilityRAGAgent] Error: %s", e, exc_info=True)
            return "I apologize, but I encountered an error while assessing loan eligibility."
