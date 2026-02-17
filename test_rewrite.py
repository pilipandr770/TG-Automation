#!/usr/bin/env python
"""Simple test of rewrite_content"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from app import create_app
from app.services.publisher_service import PublisherService
from app.services.openai_service import OpenAIService
from app.services.content_fetcher import ContentFetcher
from app.services.telegram_client import TelegramClientManager

app = create_app()

async def test():
    with app.app_context():
        content = {
            'title': 'Test Article About AI',
            'content': 'This is test content for an article about artificial intelligence',
            'url': 'http://test.com',
            'source_id': 1
        }
        
        pub = PublisherService(TelegramClientManager(), OpenAIService(), ContentFetcher())
        print("Testing rewrite_content...")
        result = await pub.rewrite_content(content, 'en')
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")
        
        if result[0]:
            print(f"\n[SUCCESS] Rewritten content:")
            print(result[0][:200])
        else:
            print("[FAILED] Rewrite returned None")

asyncio.run(test())
