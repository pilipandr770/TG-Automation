"""
Coordinator Service: Orchestrates all 5 modules in a controlled round-robin cycle.

Instead of running 5 concurrent infinite loops that interfere with each other,
this coordinator executes each task sequentially:

1. Discovery (search & join channels)
2. Audience (scan messages & analyze contacts)  
3. Conversation (handle incoming PMs) - event-driven, just listening
4. Publisher (fetch RSS & publish content)
5. Invitations (send PMs to contacts)

Each task completes before the next starts, preventing resource contention.
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger('coordinator')


class CoordinatorService:
    """Orchestrates all 5 background modules in a controlled sequence."""
    
    def __init__(self, discovery, audience, conversation, publisher, invitation):
        """
        Initialize coordinator with all services.
        
        Args:
            discovery: DiscoveryService instance
            audience: AudienceService instance
            conversation: ConversationService instance
            publisher: PublisherService instance
            invitation: InvitationService instance
        """
        self.discovery = discovery
        self.audience = audience
        self.conversation = conversation
        self.publisher = publisher
        self.invitation = invitation
        
        self.cycle_count = 0
        self.start_time = datetime.utcnow()
    
    async def run_coordinator(self) -> None:
        """
        Main coordinator loop: Execute all tasks in controlled sequence.
        
        Cycle order:
        1. Discovery Service (Module 1) - ~30-60s
        2. Brief pause
        3. Audience Service (Module 2) - ~20-40s  
        4. Brief pause
        5. Conversation Service (Module 5) - already listening via event handlers
        6. Brief pause
        7. Publisher Service (Module 3) - ~20-30s
        8. Brief pause
        9. Invitation Service (Module 4) - ~10-20s
        10. Long pause before repeating
        """
        logger.info('=' * 70)
        logger.info('[COORDINATOR] Starting round-robin orchestration of 5 modules')
        logger.info('=' * 70)
        logger.info('Execution sequence:')
        logger.info('  1️⃣ Discovery (find & join channels)')
        logger.info('  2️⃣ Audience (scan messages & extract contacts)')
        logger.info('  3️⃣ Conversation (listening for incoming PMs)')
        logger.info('  4️⃣ Publisher (publish content to channel)')
        logger.info('  5️⃣ Invitations (send PMs to contacts)')
        logger.info('=' * 70)
        
        while True:
            self.cycle_count += 1
            cycle_start = datetime.utcnow()
            
            logger.info('')
            logger.info('=' * 70)
            logger.info(f'[COORDINATOR CYCLE #{self.cycle_count}] Started at {cycle_start.isoformat()}')
            logger.info('=' * 70)
            
            try:
                # ──────────────────────────────────────────────────────────
                # 1️⃣ DISCOVERY: Search for channels by keywords
                # ──────────────────────────────────────────────────────────
                logger.info('')
                logger.info('🔍 [STEP 1/5] Running Discovery cycle...')
                discovery_start = datetime.utcnow()
                
                try:
                    discovery_stats = await self.discovery.run_discovery_cycle()
                    discovery_duration = (datetime.utcnow() - discovery_start).total_seconds()
                    logger.info(f'✅ [DISCOVERY COMPLETE] Stats: {discovery_stats}')
                    logger.info(f'   ⏱️  Duration: {discovery_duration:.1f}s')
                except Exception as e:
                    logger.error(f'❌ [DISCOVERY ERROR] {type(e).__name__}: {str(e)[:100]}', exc_info=False)
                    discovery_duration = (datetime.utcnow() - discovery_start).total_seconds()
                
                # Brief pause between modules
                logger.info('⏸️  [COORDINATOR] Pause 5s before Audience scan...')
                await asyncio.sleep(5)
                
                # ──────────────────────────────────────────────────────────
                # 2️⃣ AUDIENCE: Scan messages and extract target audience
                # ──────────────────────────────────────────────────────────
                logger.info('')
                logger.info('👥 [STEP 2/5] Running Audience scan...')
                audience_start = datetime.utcnow()
                
                try:
                    audience_stats = await self.audience.run_audience_scan()
                    audience_duration = (datetime.utcnow() - audience_start).total_seconds()
                    logger.info(f'✅ [AUDIENCE COMPLETE] Stats: {audience_stats}')
                    logger.info(f'   ⏱️  Duration: {audience_duration:.1f}s')
                except Exception as e:
                    logger.error(f'❌ [AUDIENCE ERROR] {type(e).__name__}: {str(e)[:100]}', exc_info=False)
                    audience_duration = (datetime.utcnow() - audience_start).total_seconds()
                
                # Brief pause
                logger.info('⏸️  [COORDINATOR] Pause 5s before Conversation check...')
                await asyncio.sleep(5)
                
                # ──────────────────────────────────────────────────────────
                # 3️⃣ CONVERSATION: Already listening via event handlers
                # ──────────────────────────────────────────────────────────
                logger.info('')
                logger.info('💬 [STEP 3/5] Conversation Service (event-driven)')
                logger.info('   ℹ️  Conversation listens continuously for incoming PMs')
                logger.info('   ℹ️  No action needed here - event handlers are active')
                conversation_duration = 0
                
                # Brief pause
                logger.info('⏸️  [COORDINATOR] Pause 5s before Publisher...')
                await asyncio.sleep(5)
                
                # ──────────────────────────────────────────────────────────
                # 4️⃣ PUBLISHER: Fetch RSS and publish content
                # ──────────────────────────────────────────────────────────
                logger.info('')
                logger.info('📢 [STEP 4/5] Running Publisher cycle...')
                publisher_start = datetime.utcnow()
                
                try:
                    publisher_stats = await self.publisher.run_publish_cycle(max_posts=3)
                    publisher_duration = (datetime.utcnow() - publisher_start).total_seconds()
                    logger.info(f'✅ [PUBLISHER COMPLETE] Stats: {publisher_stats}')
                    logger.info(f'   ⏱️  Duration: {publisher_duration:.1f}s')
                except Exception as e:
                    logger.error(f'❌ [PUBLISHER ERROR] {type(e).__name__}: {str(e)[:100]}', exc_info=False)
                    publisher_duration = (datetime.utcnow() - publisher_start).total_seconds()
                
                # Brief pause
                logger.info('⏸️  [COORDINATOR] Pause 5s before Invitations...')
                await asyncio.sleep(5)
                
                # ──────────────────────────────────────────────────────────
                # 5️⃣ INVITATIONS: Send invitation PMs
                # ──────────────────────────────────────────────────────────
                logger.info('')
                logger.info('💌 [STEP 5/5] Running Invitations batch...')
                invitation_start = datetime.utcnow()
                
                try:
                    invitation_stats = await self.invitation.run_invitation_batch(limit=10)
                    invitation_duration = (datetime.utcnow() - invitation_start).total_seconds()
                    logger.info(f'✅ [INVITATIONS COMPLETE] Stats: {invitation_stats}')
                    logger.info(f'   ⏱️  Duration: {invitation_duration:.1f}s')
                except Exception as e:
                    logger.error(f'❌ [INVITATIONS ERROR] {type(e).__name__}: {str(e)[:100]}', exc_info=False)
                    invitation_duration = (datetime.utcnow() - invitation_start).total_seconds()
                
                # ──────────────────────────────────────────────────────────
                # CYCLE COMPLETE
                # ──────────────────────────────────────────────────────────
                cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
                logger.info('')
                logger.info('=' * 70)
                logger.info(f'[COORDINATOR CYCLE #{self.cycle_count} COMPLETE]')
                logger.info(f'  Total cycle time: {cycle_duration:.1f}s')
                logger.info(f'  Discovery:    {discovery_duration:.1f}s')
                logger.info(f'  Audience:     {audience_duration:.1f}s')
                logger.info(f'  Conversation: (event-driven)')
                logger.info(f'  Publisher:    {publisher_duration:.1f}s')
                logger.info(f'  Invitations:  {invitation_duration:.1f}s')
                logger.info('=' * 70)
                
                # Long pause before repeating cycle
                # This gives time for fresh data and prevents hammering the API
                pause_duration = 60  # 1 minute between full cycles
                logger.info(f'⏸️  [COORDINATOR] Pausing {pause_duration}s before next cycle...')
                logger.info(f'   Next cycle will start at: {(datetime.utcnow().timestamp() + pause_duration)}')
                
                await asyncio.sleep(pause_duration)
                
            except Exception as e:
                logger.error(f'[COORDINATOR ERROR] Cycle failed: {type(e).__name__}: {str(e)}', exc_info=True)
                logger.warning('[COORDINATOR] Waiting 30s before retry...')
                await asyncio.sleep(30)


# ── Singleton accessor ───────────────────────────────────────────────────

_coordinator_instance = None

def get_coordinator_service(discovery, audience, conversation, publisher, invitation) -> CoordinatorService:
    """Get or create singleton coordinator instance."""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = CoordinatorService(discovery, audience, conversation, publisher, invitation)
    return _coordinator_instance
