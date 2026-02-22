#!/usr/bin/env python3
"""
Quick syntax check for keyword reset functionality.
This validates that the code is correctly structured without running the full test.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def check_syntax():
    """Check that the code can be imported and parsed."""
    try:
        logger.info('=' * 70)
        logger.info('[SYNTAX CHECK] Validating keyword reset code')
        logger.info('=' * 70)
        
        # Import the app
        logger.info('1️⃣  Importing Flask app...')
        from app import create_app, db
        logger.info('✅ App imported successfully')
        
        # Import models
        logger.info('2️⃣  Importing models...')
        from app.models import SearchKeyword, AppConfig
        logger.info('✅ Models imported successfully')
        
        # Import routes
        logger.info('3️⃣  Importing admin routes...')
        from app.routes import admin_routes
        logger.info('✅ Admin routes imported successfully')
        
        # Check database connection
        logger.info('4️⃣  Testing database connection...')
        app = create_app()
        with app.app_context():
            # Just try a simple query
            count = SearchKeyword.query.count()
            logger.info(f'✅ Database connection OK (found {count} keywords)')
            
            # Check table structure
            from sqlalchemy import inspect
            mapper = inspect(SearchKeyword)
            columns = [c.name for c in mapper.columns]
            logger.info(f'✅ SearchKeyword columns: {columns}')
            
            # Check if active column exists
            if 'active' in columns:
                logger.info('✅ SearchKeyword.active column exists')
            else:
                logger.error('❌ SearchKeyword.active column NOT FOUND')
                return False
        
        logger.info('=' * 70)
        logger.info('✅ [SYNTAX CHECK PASSED] All systems ready')
        logger.info('=' * 70)
        return True
        
    except Exception as e:
        logger.error('=' * 70)
        logger.error(f'❌ [SYNTAX CHECK FAILED] {type(e).__name__}: {str(e)}')
        logger.error('Full Traceback:', exc_info=True)
        logger.error('=' * 70)
        return False


if __name__ == '__main__':
    success = check_syntax()
    exit(0 if success else 1)
