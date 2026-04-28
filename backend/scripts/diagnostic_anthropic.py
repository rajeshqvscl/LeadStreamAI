import os
from anthropic import Anthropic
from dotenv import load_dotenv

# Path to .env inside app/
load_dotenv('app/.env')

def test():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY NOT FOUND")
        return

    client = Anthropic(api_key=api_key)
    models = [
        'claude-3-5-sonnet-20241022',
        'claude-3-5-sonnet-20240620',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307'
    ]

    for m in models:
        try:
            print(f"Testing {m}...")
            response = client.messages.create(
                model=m,
                max_tokens=10,
                messages=[{'role': 'user', 'content': 'Say hi'}]
            )
            print(f"SUCCESS: {m} is working!")
            return m
        except Exception as e:
            print(f"FAILED: {m} - {str(e)[:100]}")
    
    print("CRITICAL: NO MODELS WORKED")
    return None

if __name__ == "__main__":
    test()
