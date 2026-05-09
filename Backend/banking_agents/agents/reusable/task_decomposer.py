import json
from banking_agents.config.settings import get_bedrock_client, MODEL_TASK_DECOMPOSER

class TaskDecomposerAgent:
    def __init__(self):
        self.client = get_bedrock_client()
        self.model_id = MODEL_TASK_DECOMPOSER
        
    def decompose(self, query: str, intent: str) -> list[str]:
        """
        Decomposes a complex user query into a list of actionable sub-tasks using Claude Haiku.
        """
        system_prompt = f"""You are an expert banking task decomposer.
        The user has asked a query that has been broadly classified as: {intent}.
        Your job is to break this query down into a logical sequence of atomic sub-tasks that our domain agents need to answer.
        
        Return the result as a JSON array of strings. 
        Do not return any other text or markdown blocks, JUST the JSON array.
        Example: ["What is the current auto loan interest rate?", "What is the minimum credit score required for an auto loan?"]
        """
        
        messages = [
            {"role": "user", "content": [{"text": query}]}
        ]
        
        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                inferenceConfig={"temperature": 0.2}
            )
            
            output_text = response['output']['message']['content'][0]['text'].strip()
            
            # Clean up potential markdown formatting
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            if output_text.endswith("```"):
                output_text = output_text[:-3]
                
            tasks = json.loads(output_text.strip())
            if isinstance(tasks, list):
                return tasks
            return [query] # Fallback to single task
            
        except Exception as e:
            print(f"Error decomposing tasks: {e}")
            # Fallback to returning the original query as a single task
            return [query]
