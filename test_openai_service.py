#!/usr/bin/env python
"""Test OpenAI service with proper error handling"""
from dotenv import load_dotenv
import os
load_dotenv()

from openai import OpenAI

api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)

print("Testing raw OpenAI call...")
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {'role': 'system', 'content': 'You are helpful.'},
            {'role': 'user', 'content': 'Say "OK" briefly'},
        ],
        temperature=0.7,
    )
    print(f"[OK] Raw call works: {response.choices[0].message.content}")
except Exception as e:
    print(f"[ERROR] Raw call failed: {e}")
    import traceback
    traceback.print_exc()

print("\nTesting with app context...")
from app import create_app
app = create_app()

with app.app_context():
    from app.services.openai_service import OpenAIService
    
    service = OpenAIService()
    result = service.chat(
        system_prompt="Test",
        user_message="Say OK",
        module="test"
    )
    print(f"Result: {result}")
