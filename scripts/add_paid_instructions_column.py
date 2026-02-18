import sqlite3
import os
import sys

DB_PATH = os.path.join('instance', 'telegram_automation.db')

def main():
    if not os.path.exists(DB_PATH):
        print('ERROR: DB not found at', DB_PATH)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cols = [r[1] for r in cur.execute("PRAGMA table_info(paid_content)").fetchall()]
    print('Existing columns:', cols)

    if 'instructions' in cols:
        print('Column `instructions` already exists - nothing to do')
        conn.close()
        return

    try:
        cur.execute('ALTER TABLE paid_content ADD COLUMN instructions TEXT')
        conn.commit()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(paid_content)").fetchall()]
        print('Column added. New columns:', cols)
    except Exception as e:
        print('Failed to add column:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
