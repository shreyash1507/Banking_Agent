import sys
print("Python executable:", sys.executable)
print("Site packages:")
for p in sys.path:
    if "site-packages" in p or "venv" in p.lower():
        print(" ", p)

try:
    import groq
    print("\nGroq found at:", groq.__file__)
except ImportError as e:
    print("\nGroq NOT found:", e)
    print("\nInstalling now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "groq"])
    import groq
    print("Groq installed and found at:", groq.__file__)

# Now test the API
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from groq import Groq
key = os.environ.get("GROQ_API_KEY", "NOT FOUND")
print(f"\nGroq API Key: {key[:12]}...{key[-4:]}")

client = Groq(api_key=key)
try:
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Say hi in one word"}],
        max_tokens=5
    )
    print("SUCCESS:", resp.choices[0].message.content)
except Exception as e:
    print(f"API ERROR: {e}")
