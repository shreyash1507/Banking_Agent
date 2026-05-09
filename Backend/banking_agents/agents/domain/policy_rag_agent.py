from banking_agents.config.settings import get_bedrock_client, MODEL_POLICY_RAG_DEFAULT, MODEL_POLICY_RAG_FALLBACK
from banking_agents.rag.base_rag import BaseRAG

class PolicyRAGAgent:
    def __init__(self):
        self.client = get_bedrock_client()
        self.model_id = MODEL_POLICY_RAG_DEFAULT # Start with Haiku
        self.fallback_model_id = MODEL_POLICY_RAG_FALLBACK # Escalate to Sonnet if needed
        # Initialize the RAG component specifically for policies
        self.rag = BaseRAG(collection_name="policy_docs")
        
    def answer(self, task: str) -> str:
        """
        Retrieves relevant policy documents and generates an answer.
        """
        # 1. Retrieve relevant contexts
        retrieved_docs = self.rag.retrieve(task, n_results=3)
        context_text = "\n\n".join([doc["content"] for doc in retrieved_docs])
        
        system_prompt = """You are a bank policy expert. 
        Use the provided policy documents to answer the user's question accurately.
        If the answer is not contained within the documents, state that clearly.
        Do not make up policies or information. Provide precise answers.
        """
        
        prompt = f"Policy Documents Context:\n{context_text}\n\nUser Question: {task}"
        
        messages = [
            {"role": "user", "content": [{"text": prompt}]}
        ]
        
        try:
            # Generate answer using Haiku
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                inferenceConfig={"temperature": 0.1}
            )
            
            output_text = response['output']['message']['content'][0]['text'].strip()
            
            # Simple complexity check - if the model expresses low confidence or confusion, escalate to Sonnet
            if "I'm not completely sure" in output_text or "does not clearly state" in output_text:
                print("Escalating to Sonnet for complex policy query...")
                fallback_response = self.client.converse(
                    modelId=self.fallback_model_id,
                    messages=messages,
                    system=[{"text": system_prompt}],
                    inferenceConfig={"temperature": 0.1}
                )
                return fallback_response['output']['message']['content'][0]['text'].strip()
                
            return output_text
            
        except Exception as e:
            print(f"Error in PolicyRAGAgent: {e}")
            return "I apologize, but I encountered an error while retrieving the policy information."
