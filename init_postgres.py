"""
Initialize PostgreSQL database for Telegram Automation project.
Creates schema and tables.
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, event

# Load .env first
load_dotenv()

def init_postgres_db():
    """Initialize PostgreSQL database with telegram_automation schema."""
    
    print("=" * 70)
    print("Initializing PostgreSQL Database for Telegram Automation")
    print("=" * 70)
    
    db_url = os.getenv('DATABASE_URL', '')
    
    if not db_url:
        print("❌ DATABASE_URL not set in .env")
        return False
        
    print(f"\n📌 Database URL: {db_url[:60]}...")
    
    try:
        # Create engine
        engine = create_engine(db_url)
        
        # Step 1: Create schema
        print("\n📊 Step 1: Creating 'telegram_automation' schema...")
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS telegram_automation"))
            conn.commit()
            print("✓ Schema created")
        
        # Step 2: Register event listener for search_path
        print("\n📋 Step 2: Configuring database connection...")
        
        @event.listens_for(engine, "connect")
        def set_search_path(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("SET search_path TO telegram_automation")
            dbapi_conn.commit()
        
        # Step 3: Create all tables
        print("\n📋 Step 3: Creating tables in 'telegram_automation' schema...")
        
        # Import models to register them with SQLAlchemy
        from app import models  # This imports all model definitions
        from app.models import db as flask_db
        
        # Create all tables
        with engine.begin() as conn:
            # Set search_path for this connection
            conn.execute(text("SET search_path TO telegram_automation"))
            # Create all tables
            flask_db.metadata.create_all(conn)
        
        print("✓ All tables created successfully")
        
        # Step 4: Verify tables
        print("\n✅ Step 4: Verifying tables...")
        with engine.connect() as conn:
            conn.execute(text("SET search_path TO telegram_automation"))
            result = conn.execute(
                text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'telegram_automation'
                    ORDER BY table_name
                """)
            )
            tables = [row[0] for row in result.fetchall()]
        
        print(f"\n✓ Tables in schema ({len(tables)} total):")
        for table in sorted(tables):
            print(f"   • {table}")
        
        print("\n" + "=" * 70)
        print("✅ Database initialization complete!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Test connection: python test_postgres_connection.py")
        print("2. Commit and push: git add -A && git commit && git push")
        print("3. Deploy to Render.com")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = init_postgres_db()
    sys.exit(0 if success else 1)
