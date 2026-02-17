#!/usr/bin/env python
"""Test OpenAI service directly"""
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"API Key format: {api_key[:20]}...")

client = OpenAI(api_key=api_key)

try:
    print("\nTesting OpenAI API directly...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {'role': 'system', 'content': 'You are helpful.'},
            {'role': 'user', 'content': 'Say hello briefly'},
        ],
        temperature=0.7,
    )
    print("✓ Success!")
    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens: {response.usage.prompt_tokens + response.usage.completion_tokens}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
