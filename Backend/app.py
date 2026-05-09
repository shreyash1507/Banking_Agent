import uvicorn

if __name__ == "__main__":
    print("Starting Agentic Policy Bot Navigator Backend...")
    # Run the FastAPI app from the banking_agents module
    uvicorn.run("banking_agents.main:app", host="0.0.0.0", port=8000, reload=True)
