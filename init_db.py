#!/usr/bin/env python
from app import db, create_app
from app.models import *

app = create_app()

with app.app_context():
    print("Creating all tables...")
    db.create_all()
    print("✓ Database tables created successfully!")
    
    # Check if tables exist
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"\nTables created ({len(tables)}):")
    for table in sorted(tables):
        print(f"  - {table}")
