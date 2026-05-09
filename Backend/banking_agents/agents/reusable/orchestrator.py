import json
import importlib
from banking_agents.config.settings import get_bedrock_client, MODEL_ORCHESTRATOR
from banking_agents.communication.message import UserQuery, AgentContext, AgentResponse
from banking_agents.agents.reusable.intent_classifier import IntentClassifierAgent
from banking_agents.agents.reusable.task_decomposer import TaskDecomposerAgent

class OrchestratorAgent:
    def __init__(self, intents_config: dict, orchestrator_config: dict):
        self.client = get_bedrock_client()
        self.model_id = MODEL_ORCHESTRATOR # Claude 3 Sonnet
        
        self.orchestrator_config = orchestrator_config
        
        # Injected config for Intent Classifier
        self.intent_classifier = IntentClassifierAgent(intents=intents_config.get("intents", []))
        self.task_decomposer = TaskDecomposerAgent()
        
        # Dynamically load domain tools
        self.tool_instances = {}
        self.tools_schema = []
        
        self._build_dynamic_tools()

    def _build_dynamic_tools(self):
        # Always include the core reusable tools
        self.tools_schema = [
            {
                "toolSpec": {
                    "name": "classify_intent",
                    "description": "Classifies the user query into a predefined intent.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "decompose_task",
                    "description": "Breaks a query down into actionable subtasks.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "intent": {"type": "string"}
                            },
                            "required": ["query", "intent"]
                        }
                    }
                }
            }
        ]
        
        # Load domain tools from config
        domain_tools = self.orchestrator_config.get("tools", [])
        for t in domain_tools:
            name = t["name"]
            description = t["description"]
            input_prop = t["input_property"]
            module_path = t["module"]
            class_name = t["class_name"]
            
            # Dynamically import the class
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            self.tool_instances[name] = agent_class() # Instantiate
            
            # Add to schema
            self.tools_schema.append({
                "toolSpec": {
                    "name": name,
                    "description": description,
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {input_prop: {"type": "string"}},
                            "required": [input_prop]
                        }
                    }
                }
            })
            
        self.tool_config = {"tools": self.tools_schema}

    def _execute_tool(self, tool_name: str, input_data: dict) -> str:
        """Executes the mapped python function for the tool."""
        print(f"[Orchestrator] Executing tool: {tool_name} with args: {input_data}")
        try:
            if tool_name == "classify_intent":
                result = self.intent_classifier.classify(input_data['query'])
                return json.dumps(result)
            elif tool_name == "decompose_task":
                tasks = self.task_decomposer.decompose(input_data['query'], input_data['intent'])
                return json.dumps(tasks)
            elif tool_name in self.tool_instances:
                # Dynamic domain tool execution
                # Get the single key from input_data to pass to the agent
                input_val = list(input_data.values())[0]
                return self.tool_instances[tool_name].answer(input_val)
            else:
                return f"Error: Tool {tool_name} not found."
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def run(self, user_query: UserQuery, context: AgentContext) -> AgentResponse:
        system_prompt = """You are the Lead Banking Agent. 
        Your job is to resolve customer queries efficiently. 
        DO NOT answer from your own memory. 
        You MUST use your tools to classify the intent, decompose the query if complex, and consult the policy or loan experts for the answers.
        Once you have all the necessary information from the experts, synthesize a final, polite, and helpful response for the user.
        """
        
        # Build message history
        messages = [{"role": "user", "content": [{"text": user_query.query}]}]
        
        print(f"\n[Orchestrator] Starting reasoning loop for: '{user_query.query}'")
        
        while True:
            # Call Bedrock
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                toolConfig=self.tool_config,
                inferenceConfig={"temperature": 0.2}
            )
            
            output_message = response['output']['message']
            messages.append(output_message) # Add assistant's response (text or tool call) to history
            
            # If the model decided to stop (no tool calls)
            if response['stopReason'] != 'tool_use':
                final_text = next((content['text'] for content in output_message['content'] if 'text' in content), "")
                # Update context
                context.history.append({"user": user_query.query, "assistant": final_text})
                return AgentResponse(response=final_text, context=context)
                
            # Handle tool calls
            tool_results = []
            for content in output_message['content']:
                if 'toolUse' in content:
                    tool_use = content['toolUse']
                    tool_name = tool_use['name']
                    tool_input = tool_use['input']
                    tool_id = tool_use['toolUseId']
                    
                    # Execute tool locally
                    result_str = self._execute_tool(tool_name, tool_input)
                    
                    # Append result
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"json": {"result": result_str}}]
                        }
                    })
                    
            # Send tool results back to the model
            messages.append({"role": "user", "content": tool_results})
