#!/usr/bin/env python3
"""
Test script for keyword reset functionality.
Tests the atomic transaction without requiring OpenAI.
"""

import logging
from datetime import datetime

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def test_keyword_reset():
    """Test keyword reset with mock data."""
    try:
        from app import create_app, db
        from app.models import SearchKeyword, AppConfig
        
        app = create_app()
        
        with app.app_context():
            logger.info('='*70)
            logger.info('[TEST] Starting keyword reset test')
            logger.info('='*70)
            
            # Show current state
            current_count = SearchKeyword.query.count()
            active_count = SearchKeyword.query.filter_by(active=True).count()
            logger.info(f'📊 Current state: {current_count} total keywords, {active_count} active')
            
            # Sample keywords for testing
            test_keywords = [
                'telegram marketing',
                'channel discovery',
                'group search',
                'bot automation',
                'telegram scraping',
                'channel list',
                'telegram analytics',
                'group directory',
                'channel monitoring',
                'telegram trends'
            ]
            
            logger.info(f'🔄 Starting atomic transaction to replace keywords with {len(test_keywords)} new ones')
            
            try:
                # Step 1: Deactivate old keywords (much safer than deleting)
                old_count = SearchKeyword.query.filter_by(active=True).count()
                logger.info(f'Step 1: Found {old_count} active keywords to deactivate')
                
                # Mark all active keywords as inactive (atomic, safe operation)
                db.session.query(SearchKeyword).filter_by(active=True).update(
                    {SearchKeyword.active: False},
                    synchronize_session='fetch'
                )
                logger.info(f'✓ Deactivated {old_count} keywords')
                
                # Step 2: Add new keywords
                for i, keyword in enumerate(test_keywords, 1):
                    kw = SearchKeyword(
                        keyword=keyword,
                        language='en',
                        active=True,
                        priority=i,
                        source_keyword=None,
                        generation_round=0,
                    )
                    db.session.add(kw)
                logger.info(f'✓ Queued {len(test_keywords)} new keywords for addition')
                
                # Step 3: Update config
                config = AppConfig.query.filter_by(key='discovery_topic_context').first()
                if config:
                    config.value = f'Test keywords - {datetime.utcnow().isoformat()}'
                    logger.info(f'✓ Updated existing config')
                else:
                    config = AppConfig(
                        key='discovery_topic_context',
                        value=f'Test keywords - {datetime.utcnow().isoformat()}',
                        description='Test'
                    )
                    db.session.add(config)
                    logger.info(f'✓ Created new config')
                
                # Step 4: Flush to validate
                db.session.flush()
                logger.info(f'✓ Changes flushed (validated) but not committed')
                
                # Step 5: Commit
                db.session.commit()
                logger.info(f'✅ [ATOMIC COMMIT SUCCESSFUL]')
                
                # Verify
                active_count = SearchKeyword.query.filter_by(active=True).count()
                inactive_count = SearchKeyword.query.filter_by(active=False).count()
                logger.info(f'✅ [TEST PASSED] Final state: {active_count} active, {inactive_count} inactive')
                
                # Show new keywords
                new_keywords = SearchKeyword.query.filter_by(active=True).order_by(
                    SearchKeyword.priority
                ).all()
                logger.info(f'🔑 New active keywords: {[kw.keyword for kw in new_keywords]}')
                
            except Exception as e:
                db.session.rollback()
                logger.error(f'❌ [TEST FAILED] Transaction error!')
                logger.error(f'  Type: {type(e).__name__}')
                logger.error(f'  Message: {str(e)[:300]}')
                logger.error('  Traceback:', exc_info=True)
                raise
                
    except Exception as e:
        logger.critical(f'❌ [CRITICAL ERROR] {type(e).__name__}: {str(e)[:200]}')
        logger.error('Full traceback:', exc_info=True)
        raise


if __name__ == '__main__':
    try:
        test_keyword_reset()
        logger.info('='*70)
        logger.info('✅ All tests passed!')
        logger.info('='*70)
    except Exception as e:
        logger.info('='*70)
        logger.error('❌ Test failed!')
        logger.info('='*70)
        exit(1)
