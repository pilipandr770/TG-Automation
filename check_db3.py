#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('instance/telegram_automation.db')
cursor = conn.cursor()

# Get contacts columns
cursor.execute("PRAGMA table_info(contacts)")
cols = cursor.fetchall()

print("Contacts table columns:")
for col in cols:
    col_id, name, type_, notnull, default, pk = col
    print(f"  {name}: {type_}")

has_category = any(col[1] == 'category' for col in cols)
print(f"\nCategory column exists: {has_category}")

conn.close()
