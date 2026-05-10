import os
import uuid
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from banking_agents.agents.reusable.orchestrator import OrchestratorAgent
from banking_agents.agents.domain.loan_eligibility_rag_agent import LoanEligibilityRAGAgent
from banking_agents.communication.message import UserQuery, AgentContext, AgentResponse, CustomerLoanProfile
from banking_agents.guardrails.input_validator import InputValidator
from banking_agents.guardrails.output_validator import OutputValidator

app = FastAPI(
    title="Agentic Policy Bot Navigator",
    description="Multi-agent banking system powered by AWS Bedrock",
    version="1.0.0"
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Configurations
intents_path = os.path.join(os.path.dirname(__file__), "config", "intents.yaml")
with open(intents_path, "r") as f:
    intents_data = yaml.safe_load(f)

orchestrator_path = os.path.join(os.path.dirname(__file__), "config", "orchestrator.yaml")
with open(orchestrator_path, "r") as f:
    orchestrator_data = yaml.safe_load(f)

guardrails_path = os.path.join(os.path.dirname(__file__), "config", "guardrails.yaml")
with open(guardrails_path, "r") as f:
    guardrails_config = yaml.safe_load(f)

# Initialize Orchestrator with the YAML configs
orchestrator = OrchestratorAgent(
    intents_config=intents_data, 
    orchestrator_config=orchestrator_data,
    guardrails_config=guardrails_config
)

# Guardrail instances
input_validator = InputValidator(guardrails_config["input"])
output_validator = OutputValidator(guardrails_config["output"])

# Standalone loan agent (also used inside orchestrator via dynamic tools)
loan_agent = LoanEligibilityRAGAgent(guardrails_config=guardrails_config)

# In-memory store for contexts (in a real app, use Redis or a database)
session_contexts = {}

class ChatRequest(BaseModel):
    query: str
    session_id: str = None

class ChatResponse(BaseModel):
    response: Any
    final: str
    session_id: str
    intermediate_steps: Optional[List[Dict[str, Any]]] = None

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. Validate Input
        input_validator.validate(request.query)

        # 2. Create or retrieve session
        session_id = request.session_id or str(uuid.uuid4())
        
        if session_id not in session_contexts:
            context = AgentContext(session_id=session_id)
            session_contexts[session_id] = context
        else:
            context = session_contexts[session_id]

        user_query = UserQuery(query=request.query, session_id=session_id)
        
        # 3. Run orchestrator
        agent_response = orchestrator.run(user_query, context)
        
        # 4. Validate and enrich output
        final_response_text = output_validator.validate(
            agent_response.final, 
            intent=context.current_intent.name if context.current_intent else None
        )
        
        # 5. Save updated context
        session_contexts[session_id] = agent_response.context
        
        return ChatResponse(
            response=agent_response.response,
            final=final_response_text,
            session_id=session_id,
            intermediate_steps=agent_response.intermediate_steps
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Agentic Banking Backend is running."}


class LoanAssessRequest(BaseModel):
    session_id: str = None
    query: str = ""            # Optional natural language context
    profile: CustomerLoanProfile

class LoanAssessResponse(BaseModel):
    session_id: str
    eligibility_assessment: str
    profile_used: CustomerLoanProfile

@app.post("/api/v1/loan/assess", response_model=LoanAssessResponse)
async def loan_assess_endpoint(request: LoanAssessRequest):
    """
    Structured loan eligibility assessment endpoint.
    Accepts a CustomerLoanProfile with validated fields and returns
    a deterministic eligibility assessment with pre-computed FOIR, LTV, etc.
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())

        # Build the task string from the profile if no query provided
        task = request.query or (
            f"{request.profile.loan_type} loan eligibility assessment for a "
            f"{request.profile.employment_type.lower()} applicant: "
            f"monthly income ₹{request.profile.monthly_income:,.0f}, "
            f"CIBIL {request.profile.cibil_score}, "
            f"requesting ₹{request.profile.loan_amount_requested:,.0f} "
            f"for {request.profile.loan_tenure_months} months."
        )

        # Run structured assessment with pre-computed math
        result = loan_agent.answer(task=task, loan_profile=request.profile)

        # Apply output guardrail (append LOAN_ELIGIBILITY disclaimer)
        result = output_validator.validate(result, intent="LOAN_ELIGIBILITY")

        return LoanAssessResponse(
            session_id=session_id,
            eligibility_assessment=result,
            profile_used=request.profile
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid loan profile: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
