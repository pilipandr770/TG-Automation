#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import os

# Find the database
db_path = 'instance/telegram_automation.db'
if not os.path.exists(db_path):
    db_path = 'telegram_automation.db'
if not os.path.exists(db_path):
    print("Error: Could not find telegram_automation.db")
    exit(1)

print(f"Migrating {db_path}...")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get existing columns
cursor.execute("PRAGMA table_info(search_keywords)")
existing_cols = [col[1] for col in cursor.fetchall()]

new_fields = {
    'exhausted': "BOOLEAN DEFAULT 0",
    'cycles_without_new': "INTEGER DEFAULT 0",
    'generation_round': "INTEGER DEFAULT 0",
    'source_keyword': "VARCHAR(255)",
}

for field_name, field_type in new_fields.items():
    if field_name not in existing_cols:
        print(f"  Adding {field_name}...")
        try:
            cursor.execute(f"ALTER TABLE search_keywords ADD COLUMN {field_name} {field_type}")
            conn.commit()
            print(f"    [OK] {field_name} added")
        except sqlite3.OperationalError as e:
            print(f"    [ERR] {e}")

conn.close()
print("\n[OK] Migration complete!")
