from app import create_app
from app.models import PublishedPost

app = create_app()
with app.app_context():
    posts = PublishedPost.query.order_by(PublishedPost.created_at.desc()).limit(5).all()
    print('[LATEST POSTS]')
    for p in posts:
        title = p.source_title[:45] if p.source_title else 'no title'
        status = p.status or '?'
        msg_id = p.telegram_message_id or '?'
        pub_time = p.published_at or 'never'
        print(f'{title}...')
        print(f'  Status={status} | Message ID={msg_id} | Published={pub_time}')
