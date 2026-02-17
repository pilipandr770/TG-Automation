from app import create_app, db
from app.models import SearchKeyword

app = create_app()
with app.app_context():
    all_kws = SearchKeyword.query.all()
    print(f"\nAll keywords in database ({len(all_kws)}):")
    for k in all_kws:
        status = "ACTIVE" if k.active else "inactive"
        print(f"  {k.id}: '{k.keyword}' [{status}, priority={k.priority}, results={k.results_count}]")
    
    print("\n\nActive keywords (what will be searched):")
    active = SearchKeyword.query.filter_by(active=True).order_by(SearchKeyword.priority.desc()).all()
    for k in active:
        print(f"  '{k.keyword}' (priority={k.priority})")
