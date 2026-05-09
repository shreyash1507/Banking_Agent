import os
import uuid
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from banking_agents.agents.reusable.orchestrator import OrchestratorAgent
from banking_agents.communication.message import UserQuery, AgentContext

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

# Initialize Orchestrator with the YAML configs
orchestrator = OrchestratorAgent(intents_config=intents_data, orchestrator_config=orchestrator_data)

# In-memory store for contexts (in a real app, use Redis or a database)
session_contexts = {}

class ChatRequest(BaseModel):
    query: str
    session_id: str = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Create or retrieve session
        session_id = request.session_id or str(uuid.uuid4())
        
        if session_id not in session_contexts:
            context = AgentContext(session_id=session_id)
            session_contexts[session_id] = context
        else:
            context = session_contexts[session_id]

        user_query = UserQuery(query=request.query, session_id=session_id)
        
        # Run orchestrator
        agent_response = orchestrator.run(user_query, context)
        
        # Save updated context
        session_contexts[session_id] = agent_response.context
        
        return ChatResponse(
            response=agent_response.response,
            session_id=session_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Agentic Banking Backend is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
