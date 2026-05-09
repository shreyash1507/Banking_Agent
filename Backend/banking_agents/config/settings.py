import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# AWS Bedrock Model IDs
# Referencing the models requested in the plan
MODEL_INTENT_CLASSIFIER = "amazon.nova-micro-v1:0"
MODEL_TASK_DECOMPOSER = "anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_ORCHESTRATOR = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
MODEL_POLICY_RAG_DEFAULT = "anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_POLICY_RAG_FALLBACK = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
MODEL_LOAN_ELIGIBILITY = "us.   anthropic.claude-sonnet-4-5-20250929-v1:0"

def get_bedrock_client():
    """Initializes and returns an AWS Bedrock Runtime client."""
    return boto3.client(
        service_name='bedrock-runtime',
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
    )
