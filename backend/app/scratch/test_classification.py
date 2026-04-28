import os
from app.services.llm_services import EmailGenerator

def test_classification():
    llm = EmailGenerator()
    
    test_cases = [
        ("Hey, I'd love to chat more about this. When are you free?", "MEETING_REQUESTED"),
        ("This sounds cool, tell me more.", "INTERESTED"),
        ("Please stop emailing me.", "NOT_INTERESTED"),
        ("What is the pricing for this?", "NEEDS_MORE_INFO")
    ]
    
    for body, expected in test_cases:
        intent = llm.classify_email_intent(body)
        print(f"Input: {body[:50]}... -> Detected: {intent} (Expected: {expected})")

if __name__ == "__main__":
    test_classification()
