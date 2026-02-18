"""
Test PostgreSQL connection from Render.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env first
load_dotenv()

def test_postgres_connection():
    """Test PostgreSQL database connection."""
    
    db_url = os.getenv('DATABASE_URL', '')
    
    if not db_url:
        print("❌ DATABASE_URL not set in .env")
        return False
    
    print("=" * 60)
    print("Testing PostgreSQL Connection")
    print("=" * 60)
    print(f"\n📌 URL: {db_url[:60]}...")
    
    try:
        # Create engine
        engine = create_engine(db_url, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            print("\n✓ Connected to PostgreSQL")
            
            # Check server version
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✓ Server: {version.split(',')[0]}")
            
            # Check current schema
            result = conn.execute(text("SELECT current_schema()"))
            current_schema = result.fetchone()[0]
            print(f"✓ Current schema: {current_schema}")
            
            # Check if telegram_automation schema exists
            result = conn.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'telegram_automation'")
            )
            if result.fetchone():
                print("✓ 'telegram_automation' schema exists")
                
                # Count tables
                result = conn.execute(
                    text("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = 'telegram_automation'
                    """)
                )
                table_count = result.fetchone()[0]
                print(f"✓ Tables in schema: {table_count}")
            else:
                print("⚠️  'telegram_automation' schema NOT found - run init_postgres.py")
        
        print("\n" + "=" * 60)
        print("✅ PostgreSQL connection successful!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check DATABASE_URL is correct in .env")
        print("2. Verify Render PostgreSQL database is running")
        print("3. Check firewall/network settings")
        return False

if __name__ == '__main__':
    import sys
    success = test_postgres_connection()
    sys.exit(0 if success else 1)
