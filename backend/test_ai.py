import os
import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv("app/.env")

def test_claude():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    model = "claude-3-5-sonnet-20240620"
    
    print(f"Testing model: {model}")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello, respond with 'Success'"}]
        )
        print("Response Success!")
        print(response.content[0].text)
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_claude()
