"""
Migrate database to add PostMedia table for storing post images/videos.
Run this script once after deployment to enable media support in posts.
"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join('instance', 'telegram_automation.db')

def migrate_add_post_media():
    """Add PostMedia table to database."""
    if not os.path.exists(DB_PATH):
        print('ERROR: DB not found at', DB_PATH)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if table already exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='post_media'")
    if cur.fetchone():
        print('Table post_media already exists - nothing to do')
        conn.close()
        return

    try:
        # Create PostMedia table
        cur.execute('''
            CREATE TABLE post_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                published_post_id INTEGER NOT NULL,
                media_type VARCHAR(20) DEFAULT 'photo',
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER,
                caption VARCHAR(255),
                "order" INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (published_post_id) REFERENCES published_posts(id)
            )
        ''')
        
        conn.commit()
        print('Successfully created post_media table')
        
    except Exception as e:
        print(f'Failed to create table: {e}')
        conn.close()
        sys.exit(1)
    
    conn.close()
    print('Migration complete!')

if __name__ == '__main__':
    migrate_add_post_media()
