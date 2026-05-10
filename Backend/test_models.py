import boto3
import os
from dotenv import load_dotenv

load_dotenv()

candidates = [
    # Amazon Nova (APAC inference profiles)
    "apac.amazon.nova-micro-v1:0",
    "apac.amazon.nova-lite-v1:0",
    "apac.amazon.nova-pro-v1:0",
    # Amazon Nova (Global inference profiles)
    "global.amazon.nova-2-lite-v1:0",
    # Amazon Nova (bare IDs)
    "amazon.nova-micro-v1:0",
    "amazon.nova-lite-v1:0",
    "amazon.nova-pro-v1:0",
    # Anthropic Claude (Global inference profiles)
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # Anthropic Claude (APAC inference profiles)
    "apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
]

test_messages = [{"role": "user", "content": [{"text": "Say hi"}]}]

for region in ["ap-south-2", "ap-south-1"]:
    print(f"\n=== Testing region: {region} ===")
    runtime = boto3.client(
        "bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    for model_id in candidates:
        try:
            resp = runtime.converse(
                modelId=model_id,
                messages=test_messages,
                inferenceConfig={"maxTokens": 10}
            )
            reply = resp["output"]["message"]["content"][0]["text"].strip()
            print(f"  [OK]   {model_id}")
        except Exception as e:
            msg = " ".join(str(e).split(":")[1:]).strip()[:70] if ":" in str(e) else str(e)[:70]
            print(f"  [FAIL] {model_id}  ({msg})")
