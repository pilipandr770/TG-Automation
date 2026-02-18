import asyncio
import random
import logging
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Contact, InvitationTemplate, InvitationLog, AppConfig

logger = logging.getLogger(__name__)


class InvitationService:
    _instance = None

    def __init__(self, client_manager, rate_limiter):
        self.client_manager = client_manager
        self.rate_limiter = rate_limiter

    async def get_pending_contacts(self, limit=10):
        """Get contacts that haven't been invited yet."""
        contacts = Contact.query.filter_by(invitation_sent=False).limit(limit).all()
        return contacts

    async def select_template(self):
        """Select a random active invitation template."""
        templates = InvitationTemplate.query.filter_by(active=True).all()
        if not templates:
            return None
        return random.choice(templates)

    def personalize_message(self, template, contact):
        """Replace placeholders in template with contact data."""
        message = template.body
        message = message.replace('{first_name}', contact.first_name or '')
        message = message.replace('{username}', contact.username or '')
        message = message.replace('{last_name}', contact.last_name or '')
        return message.strip()

    async def send_invitation(self, contact, template):
        """Send invitation message to a contact."""
        try:
            client = await self.client_manager.get_client()
            if not client:
                logger.error('No Telegram client available')
                return False

            # Check rate limits
            if not await self.rate_limiter.acquire('send_message'):
                logger.warning(f'Rate limit reached for sending messages')
                return False

            # Personalize message
            message_text = self.personalize_message(template, contact)
            target_channel = AppConfig.get('target_channel', '@your_channel')

            # Send message
            await client.send_message(contact.telegram_id, message_text)

            # Log successful send - check if log already exists
            existing_log = InvitationLog.query.filter_by(contact_id=contact.id).first()
            if existing_log:
                # Update existing log
                existing_log.status = 'sent'
                existing_log.template_id = template.id
                existing_log.target_channel = target_channel
                existing_log.message_text = message_text
                existing_log.error_message = None
                existing_log.sent_at = datetime.utcnow()
            else:
                # Create new log
                existing_log = InvitationLog(
                    contact_id=contact.id,
                    template_id=template.id,
                    target_channel=target_channel,
                    message_text=message_text,
                    status='sent'
                )
                db.session.add(existing_log)

            # Update contact
            contact.invitation_sent = True
            contact.invitation_sent_at = datetime.utcnow()
            contact.status = 'invited'

            # Update template use count
            template.use_count += 1

            db.session.commit()
            logger.info(f'Sent invitation to contact {contact.telegram_id}')
            return True

        except IntegrityError as ie:
            # Handle UNIQUE constraint violations
            logger.error(f'Integrity error for contact {contact.telegram_id}: {ie}')
            db.session.rollback()
            
            # Try to update existing log instead
            try:
                existing_log = InvitationLog.query.filter_by(contact_id=contact.id).first()
                if existing_log:
                    existing_log.status = 'failed'
                    existing_log.error_message = f'Integrity error: {str(ie)[:200]}'
                    existing_log.sent_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f'Updated invitation log for contact {contact.id} with error status')
            except Exception as update_error:
                logger.error(f'Failed to update invitation log: {update_error}')
                db.session.rollback()
            
            return False
            
        except Exception as e:
            logger.error(f'Failed to send invitation to {contact.telegram_id}: {e}')
            db.session.rollback()
            
            # Try to log failed attempt - check if log already exists
            try:
                existing_log = InvitationLog.query.filter_by(contact_id=contact.id).first()
                if existing_log:
                    # Update existing log
                    existing_log.status = 'failed'
                    existing_log.error_message = str(e)[:500]
                    existing_log.sent_at = datetime.utcnow()
                else:
                    # Create new log
                    log = InvitationLog(
                        contact_id=contact.id,
                        template_id=template.id if template else None,
                        status='failed',
                        error_message=str(e)[:500]
                    )
                    db.session.add(log)
                
                db.session.commit()
                logger.info(f'Logged failed invitation for contact {contact.id}')
            except Exception as log_error:
                logger.error(f'Failed to log invitation error: {log_error}')
                db.session.rollback()
            
            return False

    async def run_invitation_batch(self, limit=10):
        """Send up to N invitations with random delays."""
        try:
            contacts = await self.get_pending_contacts(limit)
            if not contacts:
                logger.info('No pending contacts for invitations')
                return 0

            sent_count = 0
            min_delay = int(AppConfig.get('invitation_min_delay_seconds', '60') or '60')
            max_delay = int(AppConfig.get('invitation_max_delay_seconds', '180') or '180')

            for contact in contacts:
                try:
                    template = await self.select_template()
                    if not template:
                        logger.warning('No active templates available')
                        break

                    success = await self.send_invitation(contact, template)
                    if success:
                        sent_count += 1

                    # Random delay between invitations
                    if contact != contacts[-1]:  # Don't wait after the last one
                        delay = random.randint(min_delay, max_delay)
                        logger.debug(f'Waiting {delay} seconds before next invitation...')
                        await asyncio.sleep(delay)
                except Exception as contact_error:
                    logger.error(f'Error processing contact {contact.id}: {contact_error}')
                    # Continue to next contact
                    continue

            logger.info(f'Invitation batch completed: {sent_count}/{len(contacts)} sent')
            return sent_count
        except Exception as e:
            logger.error(f'Invitation batch error: {e}')
            db.session.rollback()
            return 0

    def _get_invitation_config(self) -> tuple:
        """Get invitation configuration from database.
        
        Returns: (batch_size, cycle_interval_seconds, min_delay, max_delay)
        """
        try:
            batch_size = int(AppConfig.get('invitation_batch_size', '5'))
            cycle_interval = int(AppConfig.get('invitation_cycle_interval_minutes', '10')) * 60
            min_delay = int(AppConfig.get('invitation_min_delay_seconds', '120'))  # 2 min
            max_delay = int(AppConfig.get('invitation_max_delay_seconds', '180'))  # 3 min
            return batch_size, cycle_interval, min_delay, max_delay
        except (TypeError, ValueError):
            return 5, 600, 120, 180  # Defaults

    async def run_forever(self) -> None:
        """Run invitation sending cycles in an infinite loop."""
        logger.info('[INVITATIONS] Starting infinite invitation loop')
        cycle_count = 0
        
        while True:
            cycle_count += 1
            try:
                # Get configuration with error recovery
                try:
                    batch_size, cycle_interval, min_delay, max_delay = self._get_invitation_config()
                except Exception as config_error:
                    logger.error(f'[INVITATIONS] Failed to read config: {config_error}, using defaults')
                    batch_size, cycle_interval, min_delay, max_delay = 5, 600, 120, 180
                
                logger.info(f'[INVITATIONS CYCLE {cycle_count}] Starting batch send...')
                
                # Get pending contacts
                try:
                    pending_count = Contact.query.filter_by(invitation_sent=False).count()
                except Exception as query_error:
                    logger.error(f'[INVITATIONS] Failed to query pending contacts: {query_error}')
                    db.session.rollback()
                    pending_count = 0
                
                if pending_count == 0:
                    logger.info('[INVITATIONS] No pending contacts to invite')
                else:
                    # Send batch of invitations
                    sent_count = await self.run_invitation_batch(limit=batch_size)
                    logger.info(f'[INVITATIONS CYCLE {cycle_count}] Complete: sent {sent_count} invitations')
                
            except Exception as e:
                logger.error(f'[INVITATIONS CYCLE {cycle_count}] ERROR: {e}', exc_info=True)
                db.session.rollback()

            try:
                batch_size, cycle_interval, min_delay, max_delay = self._get_invitation_config()
            except Exception as config_error:
                logger.error(f'[INVITATIONS] Failed to read config for sleep: {config_error}')
                cycle_interval = 600
            
            logger.info(f'[INVITATIONS] Next cycle in {cycle_interval}s...')
            await asyncio.sleep(cycle_interval)


def get_invitation_service(client_manager=None, rate_limiter=None):
    """Get or create InvitationService singleton."""
    if InvitationService._instance is None and client_manager and rate_limiter:
        InvitationService._instance = InvitationService(client_manager, rate_limiter)
    return InvitationService._instance
