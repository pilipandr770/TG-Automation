"""
Telethon Client Manager — manages a single TelegramClient instance
with StringSession for Render.com persistence (no filesystem session files).
"""

import os
import logging
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


class TelegramClientManager:
    """Singleton manager for the Telethon TelegramClient.

    Session string is persisted in the TelegramSession table so the bot
    survives Render.com container restarts.
    """

    _instance = None

    def __init__(self):
        self.client: TelegramClient | None = None
        self.api_id: int = int(os.getenv('TELEGRAM_API_ID', 0))
        self.api_hash: str = os.getenv('TELEGRAM_API_HASH', '')
        self._session_string: str | None = None
        self._connected: bool = False

    # ── Environment & DB helpers ──────────────────────────────────────────

    def load_session_from_env(self) -> bool:
        """Load StringSession from .env TELEGRAM_SESSION_STRING.
        
        This is the primary method - loads saved session without DB access.
        Returns True if a session was found and loaded.
        """
        session_string = os.getenv('TELEGRAM_SESSION_STRING')
        if session_string:
            self._session_string = session_string
            logger.info('Loaded Telethon session from .env (TELEGRAM_SESSION_STRING)')
            return True
        return False

    def load_session_from_db(self) -> bool:
        """Load StringSession from the database.

        Returns True if a session was found and loaded.
        """
        try:
            from app.models import TelegramSession

            session = TelegramSession.query.filter_by(
                session_name='default', is_active=True
            ).first()
            if session and session.session_string:
                self._session_string = session.session_string
                self.api_id = session.api_id or self.api_id
                self.api_hash = session.api_hash or self.api_hash
                logger.info('Loaded Telethon session from database')
                return True

            logger.info('No active session found in database')
            return False
        except Exception as e:
            logger.error('Failed to load session from DB: %s', e)
            return False

    def save_session_to_db(self) -> bool:
        """Persist the current StringSession back to the database.

        Returns True on success.
        """
        try:
            from app import db
            from app.models import TelegramSession

            if self.client is None:
                logger.warning('No client – nothing to save')
                return False

            session_string = self.client.session.save()

            record = TelegramSession.query.filter_by(
                session_name='default'
            ).first()
            if record:
                record.session_string = session_string
                record.api_id = self.api_id
                record.api_hash = self.api_hash
                record.is_active = True
                record.last_connected = datetime.utcnow()
                record.updated_at = datetime.utcnow()
            else:
                record = TelegramSession(
                    session_name='default',
                    session_string=session_string,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    is_active=True,
                    last_connected=datetime.utcnow(),
                )
                db.session.add(record)

            db.session.commit()
            logger.info('Telethon session saved to database')
            
            # Also save to .env for persistence across restarts
            self.save_session_to_env()
            
            return True
        except Exception as e:
            logger.error('Failed to save session to DB: %s', e)
            return False

    def save_session_to_env(self) -> bool:
        """Persist the current StringSession to .env file.
        
        Returns True on success.
        """
        try:
            if self.client is None:
                logger.warning('No client – nothing to save')
                return False

            session_string = self.client.session.save()
            
            # Read current .env
            env_file = '.env'
            if not os.path.exists(env_file):
                logger.warning('.env file not found')
                return False
            
            with open(env_file, 'r', encoding='utf-8') as f:
                env_content = f.read()
            
            # Check if TELEGRAM_SESSION_STRING exists
            if 'TELEGRAM_SESSION_STRING=' in env_content:
                # Replace existing
                lines = env_content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith('TELEGRAM_SESSION_STRING='):
                        new_lines.append(f'TELEGRAM_SESSION_STRING={session_string}')
                    else:
                        new_lines.append(line)
                env_content = '\n'.join(new_lines)
            else:
                # Add after TELEGRAM_PHONE
                lines = env_content.split('\n')
                new_lines = []
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if line.startswith('TELEGRAM_PHONE='):
                        new_lines.append(f'TELEGRAM_SESSION_STRING={session_string}')
                env_content = '\n'.join(new_lines)
            
            # Write back
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            logger.info('Telethon session saved to .env')
            return True
        except Exception as e:
            logger.error('Failed to save session to .env: %s', e)
            return False

    # ── Client lifecycle ─────────────────────────────────────────────────

    async def get_client(self) -> TelegramClient | None:
        """Return an active, connected TelegramClient.

        Creates the client on first call.  Re-connects if the connection
        was lost.
        """
        if not self.api_id or not self.api_hash:
            logger.error(
                'TELEGRAM_API_ID / TELEGRAM_API_HASH not configured'
            )
            return None

        try:
            # First time — build a new client
            if self.client is None:
                # Try to load session from .env first (preferred)
                if not self._session_string:
                    self.load_session_from_env()
                
                # If not in .env, try database
                if not self._session_string:
                    self.load_session_from_db()
                
                session = StringSession(self._session_string or '')
                self.client = TelegramClient(
                    session, self.api_id, self.api_hash
                )

            # Connect / reconnect
            if not self.client.is_connected():
                await self.client.connect()
                self._connected = True
                logger.info('Telethon client connected')

                # Persist the (possibly updated) session string
                self.save_session_to_db()

            return self.client
        except Exception as e:
            logger.error('Failed to get Telethon client: %s', e)
            self._connected = False
            return None

    async def disconnect(self) -> None:
        """Gracefully disconnect the client and persist the session."""
        if self.client is not None:
            try:
                self.save_session_to_db()
                await self.client.disconnect()
                logger.info('Telethon client disconnected')
            except Exception as e:
                logger.error('Error during disconnect: %s', e)
            finally:
                self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.client is not None and self.client.is_connected()


# ── Singleton accessor ───────────────────────────────────────────────────

def get_telegram_client_manager() -> TelegramClientManager:
    if TelegramClientManager._instance is None:
        TelegramClientManager._instance = TelegramClientManager()
    return TelegramClientManager._instance
