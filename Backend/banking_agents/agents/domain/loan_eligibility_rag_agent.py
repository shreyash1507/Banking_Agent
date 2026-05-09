from banking_agents.config.settings import get_bedrock_client, MODEL_LOAN_ELIGIBILITY
from banking_agents.rag.base_rag import BaseRAG

class LoanEligibilityRAGAgent:
    def __init__(self):
        self.client = get_bedrock_client()
        self.model_id = MODEL_LOAN_ELIGIBILITY # Use Sonnet strictly
        self.rag = BaseRAG(collection_name="loan_docs")
        
    def answer(self, task: str) -> str:
        """
        Retrieves relevant loan eligibility documents and generates an answer using strong numerical reasoning.
        """
        # 1. Retrieve relevant contexts
        retrieved_docs = self.rag.retrieve(task, n_results=4)
        context_text = "\n\n".join([doc["content"] for doc in retrieved_docs])
        
        system_prompt = """You are an expert Loan Eligibility Assessor for the bank.
        Use the provided loan guidelines to answer the user's eligibility question.
        Pay very close attention to numerical thresholds (income, CIBIL scores, tenure limits, margins).
        Perform step-by-step mathematical reasoning if required to determine eligibility.
        If there are multiple criteria, explicitly list which are met and which are not.
        Do not guess or assume. If the information is incomplete to make a final decision, explain what is missing.
        """
        
        prompt = f"Loan Guidelines Context:\n{context_text}\n\nUser Question: {task}"
        
        messages = [
            {"role": "user", "content": [{"text": prompt}]}
        ]
        
        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                inferenceConfig={"temperature": 0.0} # Zero temperature for strict rule evaluation
            )
            
            return response['output']['message']['content'][0]['text'].strip()
            
        except Exception as e:
            print(f"Error in LoanEligibilityRAGAgent: {e}")
            return "I apologize, but I encountered an error while assessing loan eligibility."
