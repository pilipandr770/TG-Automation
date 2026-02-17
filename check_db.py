#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('telegram_automation.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(contacts);')
cols = cursor.fetchall()

print('Contact table columns:')
for col in cols:
    col_id, col_name, col_type, notnull, default, pk = col
    print(f'  {col_name}: {col_type}')

# Check if category column exists
has_category = any(col[1] == 'category' for col in cols)
print(f'\nCategory column exists: {has_category}')

if not has_category:
    print('\n⚠️ NEEDS MIGRATION: Run alembic upgrade head')
else:
    print('\n✓ Database schema is up to date')

conn.close()
