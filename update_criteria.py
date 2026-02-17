#!/usr/bin/env python
"""Update criteria to lower the min_confidence threshold."""
from app import create_app, db
from app.models import AudienceCriteria

app = create_app()
with app.app_context():
    print("Updating audience criteria min_confidence...")
    
    criteria_list = AudienceCriteria.query.all()
    for c in criteria_list:
        old_confidence = c.min_confidence
        c.min_confidence = 0.5  # Lower threshold to catch more real users
        db.session.commit()
        print(f"✓ '{c.name}': {old_confidence} → {c.min_confidence}")
    
    print(f"\n✓ Updated {len(criteria_list)} criteria")
    print("Contacts with confidence >= 0.5 will now be saved!")
    print("Secondary matching stage disabled - categorization is sufficient.")
    print("All target_audience users will now be saved.")
