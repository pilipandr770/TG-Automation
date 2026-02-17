#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('instance/telegram_automation.db')
cursor = conn.cursor()

# Check if category column exists
cursor.execute("PRAGMA table_info(contacts)")
cols = [col[1] for col in cursor.fetchall()]

if 'category' not in cols:
    print("Adding category column to contacts table...")
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN category VARCHAR(20) DEFAULT 'target_audience'")
        conn.commit()
        print("✓ Category column added successfully")
    except sqlite3.OperationalError as e:
        print(f"✗ Error: {e}")
else:
    print("✓ Category column already exists")

# Verify
cursor.execute("PRAGMA table_info(contacts)")
cols = cursor.fetchall()
print("\nUpdated columns:")
for col in cols:
    print(f"  {col[1]}: {col[2]}")

conn.close()
print("\n✓ Database migration complete!")
