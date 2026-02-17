#!/usr/bin/env python
"""Test discovery cycle directly."""
import asyncio
from app import create_app
from app.services.discovery_service import get_discovery_service

async def test_cycle():
    app = create_app()
    
    with app.app_context():
        discovery = get_discovery_service()
        print('[TEST] Running discovery cycle...')
        stats = await discovery.run_discovery_cycle()
        print(f'[TEST] Results: {stats}')

if __name__ == '__main__':
    asyncio.run(test_cycle())
