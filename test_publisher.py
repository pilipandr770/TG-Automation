#!/usr/bin/env python3
"""Test the content publishing pipeline without publishing to Telegram."""
import asyncio
import json
from app import create_app, db
from app.models import ContentSource, PublishedPost
from app.services.content_fetcher import ContentFetcher
from app.services.openai_service import get_openai_service
from datetime import datetime

async def test_publisher_pipeline():
    """Test: Fetch → Rewrite → Preview (don't actually publish)."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("CONTENT PUBLISHING PIPELINE TEST")
        print("=" * 80)
        
        # Step 1: Fetch content from RSS
        print("\n[STEP 1] Fetching content from RSS feeds...")
        sources = ContentSource.query.filter_by(active=True).all()
        fetcher = ContentFetcher()
        all_items = []
        
        for source in sources[:2]:  # Test with first 2 sources
            print(f"\n  Fetching from: {source.name}")
            items = fetcher.fetch_source(source)
            print(f"  ✓ Got {len(items)} items")
            
            for item in items[:1]:  # Take only first item from each source
                item['source_id'] = source.id
                item['language'] = source.language
                all_items.append(item)
                print(f"    Title: {item['title'][:60]}...")
        
        if not all_items:
            print("\n❌ No content fetched. Check RSS feeds.")
            return
        
        # Step 2: Rewrite content with OpenAI
        print("\n[STEP 2] Rewriting content with OpenAI...")
        openai = get_openai_service()
        
        for i, item in enumerate(all_items[:1], 1):  # Test with first item
            print(f"\n  Item {i}: {item['title'][:60]}")
            
            system_prompt = (
                'You are a Telegram content editor. Rewrite this article as an engaging '
                'Telegram post (max 4000 characters). Make it interesting, add relevant emojis, '
                'use formatting (bold, italic), and include a call-to-action. '
                'Format the output nicely with line breaks.'
            )
            
            user_message = (
                f"Title: {item['title']}\n\n"
                f"Content: {item['content'][:1500]}\n\n"
                f"Source: {item['url']}"
            )
            
            print("  Calling OpenAI...")
            result = openai.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                module='publisher_test'
            )
            
            if result.get('content'):
                rewritten = result['content']
                char_count = len(rewritten)
                
                print(f"  ✓ Rewritten ({char_count} chars)")
                print(f"  Tokens used: {result.get('prompt_tokens', 0)} + {result.get('completion_tokens', 0)}")
                print(f"  Cost: ${result.get('cost', 0):.4f}")
                
                # Display preview
                print(f"\n  PREVIEW:")
                print("  " + "─" * 76)
                for line in rewritten[:500].split('\n'):
                    print(f"  {line}")
                if len(rewritten) > 500:
                    print(f"  ... ({char_count - 500} more chars)")
                print("  " + "─" * 76)
                
                # Save as draft
                post = PublishedPost(
                    source_id=item.get('source_id'),
                    source_url=item['url'],
                    source_title=item['title'],
                    original_content=item['content'][:2000],
                    rewritten_content=rewritten,
                    telegram_message_id=None,
                    telegram_channel=None,
                    language=item.get('language', 'en'),
                    status='draft',
                    tokens_used=result.get('prompt_tokens', 0) + result.get('completion_tokens', 0)
                )
                db.session.add(post)
                db.session.commit()
                
                print(f"\n  ✓ Saved as draft (ID: {post.id})")
            else:
                print(f"  ❌ Failed to rewrite: {result.get('error', 'Unknown error')}")
        
        # Step 3: Show statistics
        print("\n[STEP 3] Publishing Statistics")
        print("=" * 80)
        
        all_posts = PublishedPost.query.all()
        published = PublishedPost.query.filter_by(status='published').count()
        drafts = PublishedPost.query.filter_by(status='draft').count()
        failed = PublishedPost.query.filter_by(status='failed').count()
        
        print(f"  Total posts: {len(all_posts)}")
        print(f"  ├─ Published: {published}")
        print(f"  ├─ Drafts: {drafts}")
        print(f"  └─ Failed: {failed}")
        
        if all_posts:
            total_tokens = sum(p.tokens_used or 0 for p in all_posts)
            print(f"\n  Total tokens used: {total_tokens}")
            
            # Estimate cost (gpt-4o-mini: $0.15 per 1M input, $0.60 per 1M output)
            # Assuming 40% input, 60% output
            estimated_cost = (total_tokens * 0.4 * 0.15 + total_tokens * 0.6 * 0.60) / 1_000_000
            print(f"  Estimated cost: ${estimated_cost:.4f}")
        
        print("\n" + "=" * 80)
        print("✅ Test complete!")
        print("\nTO PUBLISH CONTENT:")
        print("  1. Set 'target_channel' in /admin/settings")
        print("  2. Call: POST /api/publish/trigger")
        print("  3. Or trigger via admin dashboard")

if __name__ == '__main__':
    asyncio.run(test_publisher_pipeline())
