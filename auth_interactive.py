#!/usr/bin/env python3
"""
Interactive Telegram authentication script.
Establishes a fresh session and saves it to the database.
Run this once to authenticate, then telethon_runner can use the saved session.
"""
import asyncio
import logging
import sys
from app import create_app
from app.services.telegram_client import TelegramClientManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('auth_interactive')


async def main():
    """Run interactive authentication."""
    app = create_app()
    
    with app.app_context():
        client_mgr = TelegramClientManager()
        client_mgr.load_session_from_db()
        
        try:
            logger.info('Connecting to Telegram...')
            client = await client_mgr.get_client()
            
            if client is None:
                logger.error('✗ Failed to create Telegram client')
                return
            
            if await client.is_user_authorized():
                logger.info('✓ Client already authorized with valid session!')
                client_mgr.save_session_to_db()
                logger.info('Session saved to database.')
                return
            
            logger.info('\n=== INTERACTIVE AUTHENTICATION ===')
            logger.info('You will be asked for your phone, SMS code, and potentially 2FA password.')
            
            phone = input('\nEnter your phone number (with country code, e.g., +1234567890): ').strip()
            if not phone.startswith('+'):
                phone = '+' + phone
            logger.info(f'Sending code to {phone}...')
            
            await client.sign_in(phone)
            logger.info('✓ SMS code sent to your phone.')
            
            code = input('Enter the SMS code you received: ').strip()
            logger.info('Verifying SMS code...')
            
            try:
                await client.sign_in(code=code)
                logger.info('✓ Authenticated with SMS code!')
            except Exception as e:
                if '2FA' in str(e) or 'Two-Step' in str(e) or 'Two-steps' in str(e):
                    logger.info('\n⚠ Two-factor authentication is enabled.')
                    password = input('Enter your Telegram 2FA password: ').strip()
                    logger.info('Verifying 2FA password...')
                    try:
                        await client.sign_in(password=password)
                        logger.info('✓ Successfully authenticated with 2FA!')
                    except Exception as e2:
                        logger.error(f'✗ Failed 2FA authentication: {e2}')
                        return
                else:
                    logger.error(f'✗ Failed to authenticate: {e}')
                    return
            
            logger.info('\n✓ Authentication successful!')
            client_mgr.save_session_to_db()
            logger.info('✓ Session saved to database.')
            logger.info('\nYou can now start telethon_runner.py')
            
        except Exception as e:
            logger.error(f'✗ Connection error: {e}', exc_info=True)
        finally:
            await client_mgr.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
