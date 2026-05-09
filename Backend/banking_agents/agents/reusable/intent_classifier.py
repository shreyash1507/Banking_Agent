import json
from banking_agents.config.settings import get_bedrock_client, MODEL_INTENT_CLASSIFIER

class IntentClassifierAgent:
    def __init__(self, intents: list[dict]):
        self.client = get_bedrock_client()
        self.model_id = MODEL_INTENT_CLASSIFIER
        self.intents = intents
        
    def _build_prompt(self) -> str:
        intent_list = "\n".join(
            f"- {i['name']}: {i['description']}" for i in self.intents
        )
        return f"""
        You are an expert banking intent classifier.
        Classify the user's intent into exactly one of the following categories:
        {intent_list}
        - UNKNOWN: Greetings, small talk, or queries completely unrelated to banking.

        Return ONLY a raw JSON object with two keys: "intent" (string) and "confidence" (float between 0 and 1). Do not use markdown blocks.
        """
        
    def classify(self, query: str) -> dict:
        messages = [{"role": "user", "content": [{"text": query}]}]
        
        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": self._build_prompt()}],
                inferenceConfig={"temperature": 0.0}
            )
            
            output_text = response['output']['message']['content'][0]['text'].strip()
            
            # Clean markdown if present
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            if output_text.endswith("```"):
                output_text = output_text[:-3]
                
            result = json.loads(output_text.strip())
            return result
        except Exception as e:
            print(f"Error classifying intent: {e}")
            return {"intent": "UNKNOWN", "confidence": 0.0}
