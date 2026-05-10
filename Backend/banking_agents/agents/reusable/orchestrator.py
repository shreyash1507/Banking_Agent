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
    def __init__(self, intents_config: dict, orchestrator_config: dict, guardrails_config: dict):
        logger.info("[OrchestratorAgent] Initializing OrchestratorAgent...")
        self.orchestrator_config = orchestrator_config
        self.client: Groq = get_groq_client()
        self.model_id = MODEL_ORCHESTRATOR
        self.guardrails_config = guardrails_config
        
        # Guardrails setup
        oc = guardrails_config.get("orchestrator", {})
        self.max_iterations = oc.get("max_iterations", 5)
        self.max_subtasks = oc.get("max_subtasks", 4)
        self.fallback_msg = oc.get("fallback_message", "I'm sorry, I'm having trouble.")
        self.timeout = oc.get("per_hop_timeout_seconds", 30)

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
            # Pass the guardrails config if the agent supports it
            self.tool_instances[name] = agent_class(guardrails_config=self.guardrails_config)
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
                # Apply max_subtasks guardrail to prevent flooding domain agents
                if len(tasks) > self.max_subtasks:
                    logger.warning(
                        "[OrchestratorAgent._execute_tool] TaskDecomposer returned %d tasks, truncating to %d (max_subtasks).",
                        len(tasks), self.max_subtasks
                    )
                    tasks = tasks[:self.max_subtasks]
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
Synthesize a final, polite, and helpful response for the user based on the tool outputs."""

        # Groq message format: system + user history
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_query.query},
        ]

        audit_trail = []

        iteration = 0
        while iteration < self.max_iterations:
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
                    timeout=self.timeout
                )
                logger.debug("[OrchestratorAgent.run] Groq response | finish_reason: %s", response.choices[0].finish_reason)
            except Exception as e:
                import groq
                from fastapi import HTTPException
                logger.error("[OrchestratorAgent.run] Error calling Groq API: %s", e, exc_info=True)
                
                if isinstance(e, groq.RateLimitError):
                    raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")
                elif isinstance(e, groq.APITimeoutError):
                    logger.warning("[OrchestratorAgent.run] Groq API timed out. Returning fallback.")
                    return AgentResponse(
                        final=self.fallback_msg,
                        context=context,
                        audit_trail=audit_trail
                    )
                elif isinstance(e, groq.APIConnectionError):
                    raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please check your connection.")
                
                raise e

            choice = response.choices[0]
            assistant_message = choice.message

            # Append assistant turn to history (Groq format)
            messages.append({"role": "assistant", "content": assistant_message.content, "tool_calls": assistant_message.tool_calls})

            # If no tool calls → final answer
            if choice.finish_reason != "tool_calls" or not assistant_message.tool_calls:
                final_text = assistant_message.content or ""
                logger.info("[OrchestratorAgent.run] <<< Done after %d iteration(s). Returning response.", iteration)
                
                # Add final synthesis as an audit step
                audit_trail.append({
                    "step": len(audit_trail) + 1,
                    "action": "Final Synthesis",
                    "agent": "Orchestrator",
                    "input": "Synthesize all agent findings into a cohesive response.",
                    "finding": final_text
                })

                context.history.append({"user": user_query.query, "assistant": final_text})
                print(f"\n[DEBUG] AUDIT TRAIL LOG: {json.dumps(audit_trail, indent=2)}\n")
                return AgentResponse(
                    final=final_text,
                    context=context, 
                    audit_trail=audit_trail
                )

            # Execute all tool calls and add results
            for tool_call in assistant_message.tool_calls:
                tool_name  = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)
                tool_id    = tool_call.id

                logger.debug("[OrchestratorAgent.run] Tool call: '%s' (id: %s)", tool_name, tool_id)
                result_str = self._execute_tool(tool_name, tool_input)

                # Determine semantic action label
                action = "Domain Consultation"
                agent_label = tool_name
                if tool_name == "classify_intent":
                    action = "Analyzing Intent"
                    agent_label = "Classifier"
                elif tool_name == "decompose_task":
                    action = "Strategic Planning"
                    agent_label = "Planner"
                elif tool_name in self.tool_instances:
                    agent_label = type(self.tool_instances[tool_name]).__name__

                # Record audit step
                audit_trail.append({
                    "step": len(audit_trail) + 1,
                    "action": action,
                    "agent": agent_label,
                    "input": tool_input,
                    "finding": result_str
                })

                # Groq tool result format
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_id,
                    "content":      result_str,
                })

            logger.debug("[OrchestratorAgent.run] Sent %d tool result(s) back to model.", len(assistant_message.tool_calls))

        logger.warning("[OrchestratorAgent.run] Exceeded self.max_iterations (%d). Returning fallback response.", self.max_iterations)
        return AgentResponse(
            final=self.fallback_msg, 
            context=context, 
            audit_trail=audit_trail
        )

