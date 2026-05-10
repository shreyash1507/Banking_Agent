import json
import logging
import importlib
from groq import Groq
from banking_agents.config.settings import get_groq_client, MODEL_ORCHESTRATOR
from banking_agents.communication.message import UserQuery, AgentContext, AgentResponse
from banking_agents.agents.reusable.intent_classifier import IntentClassifierAgent
from banking_agents.agents.reusable.task_decomposer import TaskDecomposerAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    def __init__(self, intents_config: dict, orchestrator_config: dict):
        logger.info("[OrchestratorAgent] Initializing OrchestratorAgent...")
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_ORCHESTRATOR
        logger.info("[OrchestratorAgent] Using model: %s", self.model_id)

        self.orchestrator_config = orchestrator_config

        logger.debug("[OrchestratorAgent] Loading IntentClassifierAgent and TaskDecomposerAgent...")
        self.intent_classifier = IntentClassifierAgent(intents=intents_config.get("intents", []))
        self.task_decomposer = TaskDecomposerAgent()

        self.tool_instances = {}
        self.tools_schema = []   # Groq/OpenAI tool format

        self._build_dynamic_tools()
        logger.info("[OrchestratorAgent] Initialization complete.")

    # ------------------------------------------------------------------
    # Build tool schemas in Groq/OpenAI format
    # ------------------------------------------------------------------
    def _build_dynamic_tools(self):
        logger.debug("[OrchestratorAgent._build_dynamic_tools] Building tool schemas...")

        # Core reusable tools
        self.tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "classify_intent",
                    "description": "Classifies the user query into a predefined banking intent.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "The user query to classify."}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "decompose_task",
                    "description": "Breaks a complex banking query into a list of actionable sub-tasks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query":  {"type": "string", "description": "The original user query."},
                            "intent": {"type": "string", "description": "The classified intent of the query."},
                        },
                        "required": ["query", "intent"],
                    },
                },
            },
        ]

        # Dynamically load domain tools from YAML config
        domain_tools = self.orchestrator_config.get("tools", [])
        logger.info("[OrchestratorAgent._build_dynamic_tools] Found %d domain tool(s) in config.", len(domain_tools))

        for t in domain_tools:
            name        = t["name"]
            description = t["description"]
            input_prop  = t["input_property"]
            module_path = t["module"]
            class_name  = t["class_name"]

            logger.debug("[OrchestratorAgent._build_dynamic_tools] Loading tool '%s' from %s.%s", name, module_path, class_name)
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            self.tool_instances[name] = agent_class()
            logger.info("[OrchestratorAgent._build_dynamic_tools] Tool '%s' loaded successfully.", name)

            self.tools_schema.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {input_prop: {"type": "string"}},
                        "required": [input_prop],
                    },
                },
            })

        logger.debug("[OrchestratorAgent._build_dynamic_tools] Total tools registered: %d", len(self.tools_schema))

    # ------------------------------------------------------------------
    # Tool execution dispatcher
    # ------------------------------------------------------------------
    def _execute_tool(self, tool_name: str, input_data: dict) -> str:
        logger.info("[OrchestratorAgent._execute_tool] >>> Tool: '%s' | Input: %s", tool_name, input_data)
        try:
            if tool_name == "classify_intent":
                logger.debug("[OrchestratorAgent._execute_tool] Delegating to IntentClassifierAgent.classify()")
                result = self.intent_classifier.classify(input_data["query"])
                logger.info("[OrchestratorAgent._execute_tool] <<< classify_intent result: %s", result)
                return json.dumps(result)

            elif tool_name == "decompose_task":
                logger.debug("[OrchestratorAgent._execute_tool] Delegating to TaskDecomposerAgent.decompose()")
                tasks = self.task_decomposer.decompose(input_data["query"], input_data["intent"])
                logger.info("[OrchestratorAgent._execute_tool] <<< decompose_task result: %s", tasks)
                return json.dumps(tasks)

            elif tool_name in self.tool_instances:
                logger.debug("[OrchestratorAgent._execute_tool] Delegating to dynamic tool: '%s'", tool_name)
                input_val = list(input_data.values())[0]
                result = self.tool_instances[tool_name].answer(input_val)
                logger.info("[OrchestratorAgent._execute_tool] <<< '%s' result: %d chars", tool_name, len(result))
                return result

            else:
                logger.warning("[OrchestratorAgent._execute_tool] Tool '%s' not found.", tool_name)
                return f"Error: Tool '{tool_name}' not found."

        except Exception as e:
            logger.error("[OrchestratorAgent._execute_tool] Error in tool '%s': %s", tool_name, e, exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"

    # ------------------------------------------------------------------
    # Main reasoning loop
    # ------------------------------------------------------------------
    def run(self, user_query: UserQuery, context: AgentContext) -> AgentResponse:
        logger.info("[OrchestratorAgent.run] >>> Starting reasoning loop for: '%s'", user_query.query)

        system_prompt = """You are the Lead Banking Agent.
Your job is to resolve customer queries efficiently.
DO NOT answer from your own knowledge or memory.
You MUST use your tools to classify the intent, decompose the query if complex, and consult the policy or loan experts for accurate answers.
Once you have all necessary information, synthesize a final, polite, and helpful response for the user."""

        # Groq message format: system + user history
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_query.query},
        ]

        iteration = 0
        MAX_ITERATIONS = 3
        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.debug("[OrchestratorAgent.run] --- Iteration #%d | Messages: %d ---", iteration, len(messages))
            logger.info("[OrchestratorAgent.run] Calling Groq API | Model: %s", self.model_id)

            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    tools=self.tools_schema,
                    tool_choice="auto",
                    temperature=0.2,
                )
                logger.debug("[OrchestratorAgent.run] Groq response | finish_reason: %s", response.choices[0].finish_reason)
            except Exception as e:
                logger.error("[OrchestratorAgent.run] Error calling Groq API: %s", e, exc_info=True)
                raise e

            choice = response.choices[0]
            assistant_message = choice.message

            # Append assistant turn to history (Groq format)
            messages.append({"role": "assistant", "content": assistant_message.content, "tool_calls": assistant_message.tool_calls})

            # If no tool calls → final answer
            if choice.finish_reason != "tool_calls" or not assistant_message.tool_calls:
                final_text = assistant_message.content or ""
                logger.info("[OrchestratorAgent.run] <<< Done after %d iteration(s). Returning response.", iteration)
                logger.debug("[OrchestratorAgent.run] Final response preview: %s...", final_text[:200])
                context.history.append({"user": user_query.query, "assistant": final_text})
                return AgentResponse(response=final_text, context=context)

            # Execute all tool calls and add results
            for tool_call in assistant_message.tool_calls:
                tool_name  = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)
                tool_id    = tool_call.id

                logger.debug("[OrchestratorAgent.run] Tool call: '%s' (id: %s)", tool_name, tool_id)
                result_str = self._execute_tool(tool_name, tool_input)

                # Groq tool result format
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_id,
                    "content":      result_str,
                })

            logger.debug("[OrchestratorAgent.run] Sent %d tool result(s) back to model.", len(assistant_message.tool_calls))

        logger.warning("[OrchestratorAgent.run] Exceeded MAX_ITERATIONS (%d). Returning fallback response.", MAX_ITERATIONS)
        fallback_msg = "I'm sorry, but I'm having trouble completing your request after multiple steps. Please try rephrasing your query."
        return AgentResponse(response=fallback_msg, context=context)
