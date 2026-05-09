import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# AWS Bedrock Model IDs
# Referencing the models requested in the plan
MODEL_INTENT_CLASSIFIER = "amazon.nova-micro-v1:0"
MODEL_TASK_DECOMPOSER = "anthropic.claude-3-haiku-20240307-v1:0"
MODEL_ORCHESTRATOR = "anthropic.claude-3-sonnet-20240229-v1:0"
MODEL_POLICY_RAG_DEFAULT = "anthropic.claude-3-haiku-20240307-v1:0"
MODEL_POLICY_RAG_FALLBACK = "anthropic.claude-3-sonnet-20240229-v1:0"
MODEL_LOAN_ELIGIBILITY = "anthropic.claude-3-sonnet-20240229-v1:0"

def get_bedrock_client():
    """Initializes and returns an AWS Bedrock Runtime client."""
    return boto3.client(
        service_name='bedrock-runtime',
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
    )
