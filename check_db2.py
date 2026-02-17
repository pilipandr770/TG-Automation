#!/usr/bin/env python
import sqlite3
import os

# List all db files
print("Database files found:")
for f in os.listdir('.'):
    if f.endswith('.db'):
        print(f"  - {f} ({os.path.getsize(f)} bytes)")

# Connect to the latest modified db
db_file = max([f for f in os.listdir('.') if f.endswith('.db')], key=lambda f: os.path.getmtime(f))
print(f"\nUsing: {db_file}")

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"\nTables in database: {len(tables)}")

# Get contacts columns
cursor.execute("PRAGMA table_info(contacts)")
cols = cursor.fetchall()
print("\nContacts table columns:")
for col in cols:
    print(f"  {col[1]}: {col[2]}")

has_category = any(col[1] == 'category' for col in cols)
print(f"\nCategory column exists: {has_category}")

conn.close()
