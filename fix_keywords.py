from app import create_app, db
from app.models import SearchKeyword

app = create_app()
with app.app_context():
    # Delete the useless generic keyword
    SearchKeyword.query.filter_by(keyword="girls, love, relationships, dating, acquaintances, family").delete()
    
    # Delete the combined keyword
    SearchKeyword.query.filter_by(keyword="photography,travel").delete()
    
    # Add proper individual keywords
    keywords_to_add = [
        ("photography", 15),
        ("travel", 14),
        ("business", 13),
        ("marketing", 12),
        ("crypto", 11),
        ("trading", 10),
        ("technology", 9),
        ("startup", 8),
    ]
    
    for keyword_text, priority in keywords_to_add:
        existing = SearchKeyword.query.filter_by(keyword=keyword_text).first()
        if not existing:
            kw = SearchKeyword(keyword=keyword_text, priority=priority, active=True, language='EN')
            db.session.add(kw)
            print(f"Added: '{keyword_text}' (priority={priority})")
        else:
            print(f"Already exists: '{keyword_text}'")
    
    db.session.commit()
    
    # Show result
    print(f"\n✓ Keywords updated!")
    active = SearchKeyword.query.filter_by(active=True).order_by(SearchKeyword.priority.desc()).all()
    print(f"\nActive keywords for discovery ({len(active)}):")
    for k in active:
        print(f"  • {k.keyword} (priority={k.priority})")
