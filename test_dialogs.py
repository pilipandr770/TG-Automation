#!/usr/bin/env python
"""Alternative approach - find channels from dialogs and explore mode."""
import asyncio
import logging
from app import create_app
from app.services.telegram_client import get_telegram_client_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_dialogs():
    app = create_app()
    
    with app.app_context():
        client_mgr = get_telegram_client_manager()
        client_mgr.load_session_from_db()
        client = await client_mgr.get_client()
        
        if not client:
            logger.error('No client')
            return
        
        logger.info('Connected!')
        
        # Method 1: Get all dialogs
        logger.info('\nMethod 1: iter_dialogs() - getting user\'s chat list...')
        channels_found = {}
        try:
            count = 0
            async for dialog in client.iter_dialogs(limit=20):
                count += 1
                entity = dialog.entity
                if hasattr(entity, 'title'):
                    logger.info(f'  {count}. {entity.title} (id={entity.id})')
                    if hasattr(entity, 'username'):
                        logger.info(f'     @{entity.username}')
        except Exception as e:
            logger.error(f'Dialog error: {e}')
        
        # Method 2: Try GetFeedChannels for recommendations
        logger.info('\nMethod 2: GetFeedChannels - getting channel recommendations...')
        try:
            from telethon import functions
            result = await client(functions.channels.GetFeedChannelsRequest())
            logger.info(f'  Found {len(result.channels)} channels')
            for i, chat in enumerate(result.channels[:5]):
                logger.info(f'    {i+1}. {getattr(chat, "title", "N/A")} (id={chat.id})')
        except Exception as e:
            logger.error(f'  GetFeedChannels error: {e}')
        
        # Method 3: Try SearchRequest to search in joined chats
        logger.info('\nMethod 3: SearchRequest in specific peer...')
        try:
            from telethon import functions, types
            # Try searching in "All Chats"
            result = await client(functions.messages.SearchRequest(
                peer=types.InputPeerEmpty(),
                q='photography',
                filter=types.InputMessagesFilterChannels(),  # Filter for channels only
                min_date=0,
                max_date=0,
                offset_id=0,
                add_offset=0,
                limit=50,
                max_id=0,
                min_id=0,
                hash=0,
            ))
            if hasattr(result, 'chats'):
                logger.info(f'  Found {len(result.chats)} channels')
                for chat in result.chats[:5]:
                    logger.info(f'    - {getattr(chat, "title", "N/A")}')
        except Exception as e:
            logger.error(f'  SearchRequest error: {e}')
        
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(test_dialogs())
