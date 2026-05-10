import boto3
import os
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    "bedrock",
    region_name="ap-south-1",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)

print("=== CROSS-REGION INFERENCE PROFILES (ap-south-1) ===")
print(f"{'Profile ID':<55} {'ARN'}")
print("-" * 140)
try:
    profiles = client.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
    for p in profiles["inferenceProfileSummaries"]:
        pid = p["inferenceProfileId"]
        arn = p["inferenceProfileArn"]
        status = p["status"]
        if "claude" in pid.lower() or "nova" in pid.lower():
            print(f"  {pid:<55} {arn}   [{status}]")
except Exception as e:
    print(f"  Error: {e}")
