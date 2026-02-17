#!/usr/bin/env python
"""Test Telegram channel search API."""
import asyncio
import logging
from app import create_app, db
from app.services.telegram_client import get_telegram_client_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_search():
    app = create_app()
    
    with app.app_context():
        client_mgr = get_telegram_client_manager()
        client_mgr.load_session_from_db()
        client = await client_mgr.get_client()
        
        if not client:
            logger.error('No client')
            return
        
        if not client.is_connected():
            logger.error('Not connected')
            return
            
        logger.info('Connected!')
        
        # Test search
        keyword = 'photography'
        logger.info(f'Test 1: SearchGlobalRequest for "{keyword}"...')
        
        try:
            from telethon import functions, types
            
            result = await client(functions.messages.SearchGlobalRequest(
                q=keyword,
                offset_rate=0,
                offset_peer=types.InputPeerEmpty(),
                offset_id=0,
                limit=20,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=0,
            ))
            
            logger.info(f'  Result: {len(result.chats) if hasattr(result, "chats") else 0} chats found')
            if hasattr(result, 'chats') and result.chats:
                for chat in result.chats[:3]:
                    logger.info(f'    - {getattr(chat, "title", "N/A")} (id={chat.id})')
        except Exception as e:
            logger.error(f'  Error: {e}')
        
        # Test 2: SearchRequest
        logger.info(f'\nTest 2: SearchRequest for "{keyword}"...')
        try:
            result = await client(functions.messages.SearchRequest(
                peer=types.InputPeerEmpty(),
                q=keyword,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=0,
                offset_id=0,
                add_offset=0,
                limit=20,
                max_id=0,
                min_id=0,
                hash=0,
            ))
            
            logger.info(f'  Result: {len(result.chats) if hasattr(result, "chats") else 0} chats found')
            if hasattr(result, 'chats') and result.chats:
                for chat in result.chats[:3]:
                    logger.info(f'    - {getattr(chat, "title", "N/A")} (id={chat.id})')
        except Exception as e:
            logger.error(f'  Error: {e}')
        
        # Test 3: Try with hashtag
        keyword_hash = '#photography'
        logger.info(f'\nTest 3: SearchRequest for "{keyword_hash}"...')
        try:
            result = await client(functions.messages.SearchRequest(
                peer=types.InputPeerEmpty(),
                q=keyword_hash,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=0,
                offset_id=0,
                add_offset=0,
                limit=20,
                max_id=0,
                min_id=0,
                hash=0,
            ))
            
            logger.info(f'  Result: {len(result.chats) if hasattr(result, "chats") else 0} chats found')
            if hasattr(result, 'chats') and result.chats:
                for chat in result.chats[:3]:
                    logger.info(f'    - {getattr(chat, "title", "N/A")} (id={chat.id})')
        except Exception as e:
            logger.error(f'  Error: {e}')
        
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(test_search())
