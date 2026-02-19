import os
import logging
import secrets
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, current_app, jsonify
)
from flask_login import login_required
from werkzeug.utils import secure_filename
from telethon import types, functions
from app import db, csrf
from app.models import (
    SearchKeyword, DiscoveredChannel, AudienceCriteria, Contact,
    InvitationTemplate, InvitationLog, ContentSource, PublishedPost,
    PaidContent, Conversation, ConversationMessage, StarTransaction,
    AppConfig, TelegramSession, TaskLog, OpenAIUsageLog, PostMedia
)

admin_bp = Blueprint('admin', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)


# ─── Diagnostics ───────────────────────────────────────────────────────────────

@admin_bp.route('/status')
@login_required
def status():
    """Diagnostic endpoint to check database and system status."""
    status_info = {
        'timestamp': datetime.utcnow().isoformat(),
        'user': current_user.username,
        'tables': {},
        'config_keys': [],
        'errors': []
    }
    
    # Check table counts
    try:
        status_info['tables']['users'] = User.query.count()
        status_info['tables']['app_config'] = AppConfig.query.count()
        status_info['tables']['search_keywords'] = SearchKeyword.query.count()
        status_info['tables']['discovered_channels'] = DiscoveredChannel.query.count()
        status_info['tables']['contacts'] = Contact.query.count()
        status_info['tables']['conversations'] = Conversation.query.count()
    except Exception as e:
        status_info['errors'].append(f'Database error: {str(e)}')
    
    # Check key config values
    try:
        config = AppConfig.query.all()
        status_info['config_keys'] = [c.key for c in config]
        status_info['business_goal'] = AppConfig.get('business_goal', 'NOT SET')
    except Exception as e:
        status_info['errors'].append(f'Config error: {str(e)}')
    
    return jsonify(status_info)


# ─── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@login_required
def dashboard():
    stats = {
        'channels_found': DiscoveredChannel.query.count(),
        'channels_joined': DiscoveredChannel.query.filter_by(is_joined=True).count(),
        'contacts_total': Contact.query.count(),
        'contacts_invited': Contact.query.filter_by(invitation_sent=True).count(),
        'invitations_sent': InvitationLog.query.count(),
        'invitations_failed': InvitationLog.query.filter_by(status='failed').count(),
        'posts_published': PublishedPost.query.filter_by(status='published').count(),
        'content_sources': ContentSource.query.filter_by(active=True).count(),
        'conversations_active': Conversation.query.filter_by(status='active').count(),
        'total_stars': db.session.query(db.func.coalesce(db.func.sum(StarTransaction.amount_stars), 0)).scalar(),
        'paid_content_items': PaidContent.query.filter_by(active=True).count(),
        'keywords_active': SearchKeyword.query.filter_by(active=True).count(),
    }

    recent_logs = TaskLog.query.order_by(TaskLog.started_at.desc()).limit(10).all()
    recent_contacts = Contact.query.order_by(Contact.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html', stats=stats,
                           recent_logs=recent_logs, recent_contacts=recent_contacts)


# ─── Module 1: Keywords ───────────────────────────────────────────────────────

@admin_bp.route('/keywords', methods=['GET', 'POST'])
@login_required
def keywords():
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').strip()
        language = request.form.get('language', 'en')
        priority = int(request.form.get('priority', 0))

        if keyword:
            kw = SearchKeyword(keyword=keyword, language=language, priority=priority)
            db.session.add(kw)
            db.session.commit()
            flash(f'Keyword "{keyword}" added.', 'success')
        return redirect(url_for('admin.keywords'))

    all_keywords = SearchKeyword.query.order_by(SearchKeyword.priority.desc(),
                                                 SearchKeyword.created_at.desc()).all()
    return render_template('admin/keywords.html', keywords=all_keywords)


@admin_bp.route('/keywords/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_keyword(id):
    kw = db.session.get(SearchKeyword, id)
    if kw:
        kw.active = not kw.active
        db.session.commit()
        flash(f'Keyword "{kw.keyword}" {"activated" if kw.active else "deactivated"}.', 'info')
    return redirect(url_for('admin.keywords'))


@admin_bp.route('/keywords/<int:id>/delete', methods=['POST'])
@login_required
def delete_keyword(id):
    kw = db.session.get(SearchKeyword, id)
    if kw:
        db.session.delete(kw)
        db.session.commit()
        flash(f'Keyword "{kw.keyword}" deleted.', 'warning')
    return redirect(url_for('admin.keywords'))


# ─── Module 1: Channels ───────────────────────────────────────────────────────

@admin_bp.route('/discovery-monitor')
@login_required
def discovery_monitor():
    """Monitor discovery progress, keyword exhaustion, and Telegram limits."""
    import asyncio
    from app.services.discovery_service import DiscoveryService
    
    # Get statistics
    joined_count = DiscoveredChannel.query.filter_by(is_joined=True).count()
    total_discovered = DiscoveredChannel.query.count()
    
    # Keyword analysis
    keywords = SearchKeyword.query.all()
    keyword_stats = {
        'total': len(keywords),
        'active': SearchKeyword.query.filter_by(active=True).count(),
        'exhausted': SearchKeyword.query.filter_by(exhausted=True).count(),
        'original': SearchKeyword.query.filter_by(generation_round=0).count(),
        'regenerated': SearchKeyword.query.filter(SearchKeyword.generation_round > 0).count(),
    }
    
    # Get limit status
    discovery_service = DiscoveryService()
    try:
        # We can't use async directly in Flask, so compute limits manually
        practical_limit = 45000
        limit_status = {
            'joined_channels': joined_count,
            'practical_limit': practical_limit,
            'remaining_capacity': practical_limit - joined_count,
            'usage_percent': round((joined_count / practical_limit) * 100, 1),
            'approaching_limit': joined_count > practical_limit * 0.8,
        }
    except Exception as e:
        limit_status = {'error': str(e)}
    
    # Exhausted keywords list
    exhausted_keywords = SearchKeyword.query.filter_by(exhausted=True).all()
    active_keywords = SearchKeyword.query.filter_by(active=True, exhausted=False).all()
    
    return render_template('admin/discovery_monitor.html',
                          joined_count=joined_count,
                          total_discovered=total_discovered,
                          keyword_stats=keyword_stats,
                          limit_status=limit_status,
                          exhausted_keywords=exhausted_keywords,
                          active_keywords=active_keywords)


@admin_bp.route('/channels')
@login_required
def channels():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    q = DiscoveredChannel.query

    if status_filter:
        q = q.filter_by(status=status_filter)

    channels = q.order_by(DiscoveredChannel.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
    return render_template('admin/channels.html', channels=channels,
                           status_filter=status_filter)


@admin_bp.route('/channels/<int:id>/blacklist', methods=['POST'])
@login_required
def blacklist_channel(id):
    ch = db.session.get(DiscoveredChannel, id)
    if ch:
        ch.is_blacklisted = True
        ch.blacklist_reason = request.form.get('reason', 'Manual blacklist')
        db.session.commit()
        flash(f'Channel "{ch.title}" blacklisted.', 'warning')
    return redirect(url_for('admin.channels'))


@admin_bp.route('/channels/join-manual', methods=['POST'])
@login_required
def join_channel_manual():
    """Manually join a channel by username or link.
    
    Uses a fresh TelegramClient for each request to avoid event loop conflicts.
    """
    import asyncio
    from telethon.sessions import StringSession
    from telethon import TelegramClient
    from app.models import TelegramSession
    
    channel_input = request.form.get('channel_input', '').strip()
    logger.info(f'join_channel_manual: channel_input="{channel_input}"')
    
    if not channel_input:
        flash('Пожалуйста, введите username или ссылку на канал', 'warning')
        return redirect(url_for('admin.channels'))
    
    async def manual_join_async():
        """Async function running in fresh event loop with new TelegramClient."""
        try:
            api_id = int(os.getenv('TELEGRAM_API_ID', 0))
            api_hash = os.getenv('TELEGRAM_API_HASH', '')
            
            if not api_id or not api_hash:
                return None, 'Telegram API credentials not configured'
            
            # Load session from database
            session_record = TelegramSession.query.filter_by(
                session_name='default', is_active=True
            ).first()
            
            if not session_record or not session_record.session_string:
                logger.warning('join_channel_manual: No session in database')
                return None, 'Телеграм сессия не найдена. Требуется новая аутентификация.'
            
            logger.info('join_channel_manual: Creating fresh TelegramClient')
            session = StringSession(session_record.session_string)
            client = TelegramClient(session, api_id, api_hash)
            
            try:
                await client.connect()
                logger.info('join_channel_manual: Client connected')
                
                # Get the channel entity
                logger.info(f'join_channel_manual: Resolving entity "{channel_input}"')
                channel = await client.get_entity(channel_input)
                logger.info(f'join_channel_manual: Resolved to id={channel.id}, type={type(channel).__name__}')
                
                # Check if already in database
                existing = DiscoveredChannel.query.filter_by(
                    telegram_id=channel.id
                ).first()
                
                if existing:
                    logger.info(f'join_channel_manual: Channel already in DB: {existing.title}')
                    return None, f'Канал уже добавлен: {existing.title}'
                
                # Try to join the channel
                join_status = 'found'
                try:
                    logger.info(f'join_channel_manual: Attempting JoinChannelRequest')
                    await client(functions.channels.JoinChannelRequest(channel=channel))
                    join_status = 'joined'
                    logger.info(f'join_channel_manual: Successfully joined')
                except Exception as join_e:
                    logger.info(f'join_channel_manual: Join failed (non-critical): {join_e}')
                
                # Extract channel info
                title = getattr(channel, 'title', 'Unknown')
                username = getattr(channel, 'username', None)
                about = getattr(channel, 'about', '')
                subscribers = getattr(channel, 'participants_count', 0) or 0
                has_comments = getattr(channel, 'megagroup', False) or getattr(channel, 'gigagroup', False)
                
                # Determine channel type
                channel_type = 'channel'
                if getattr(channel, 'megagroup', False) or getattr(channel, 'gigagroup', False):
                    channel_type = 'supergroup'
                elif isinstance(channel, types.Chat):
                    channel_type = 'group'
                
                logger.info(f'join_channel_manual: Saving - title={title}, subscribers={subscribers}, type={channel_type}')
                
                # Save to database
                discovered = DiscoveredChannel(
                    telegram_id=channel.id,
                    username=username,
                    title=title,
                    description=about,
                    channel_type=channel_type,
                    subscriber_count=subscribers,
                    has_comments=has_comments,
                    is_joined=(join_status == 'joined'),
                    join_date=datetime.utcnow() if join_status == 'joined' else None,
                    status=join_status,
                    topic_match_score=1.0,
                )
                
                db.session.add(discovered)
                db.session.commit()
                logger.info(f'join_channel_manual: Saved to DB with id={discovered.id}')
                
                return discovered, f'✓ Канал добавлен: {title} ({subscribers} подписчиков)'
            
            finally:
                if client.is_connected():
                    await client.disconnect()
                    logger.info('join_channel_manual: Client disconnected')
        
        except Exception as e:
            logger.exception(f'join_channel_manual: Exception in async handler: {e}')
            error_msg = str(e)[:100]
            return None, f'Ошибка: {error_msg}'
    
    try:
        # Run in fresh event loop using asyncio.run()
        logger.info('join_channel_manual: Starting with asyncio.run()')
        result = asyncio.run(manual_join_async())
        
        if result:
            channel, message = result
            if channel:
                flash(message, 'success')
            else:
                flash(message, 'warning')
        
    except Exception as e:
        logger.exception(f'join_channel_manual: Uncaught exception: {e}')
        flash(f'Ошибка: {str(e)[:80]}', 'danger')
    
    return redirect(url_for('admin.channels'))


# ─── Module 2: Audience Criteria ──────────────────────────────────────────────

@admin_bp.route('/audience-criteria', methods=['GET', 'POST'])
@login_required
def audience_criteria():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        keywords_text = request.form.get('keywords', '')
        openai_prompt = request.form.get('openai_prompt', '')
        min_confidence = float(request.form.get('min_confidence', 0.7))

        if name:
            ac = AudienceCriteria(
                name=name, keywords=keywords_text,
                openai_prompt=openai_prompt, min_confidence=min_confidence
            )
            db.session.add(ac)
            db.session.commit()
            flash(f'Criteria "{name}" added.', 'success')
        return redirect(url_for('admin.audience_criteria'))

    criteria = AudienceCriteria.query.order_by(AudienceCriteria.created_at.desc()).all()
    return render_template('admin/audience_criteria.html', criteria=criteria)


@admin_bp.route('/audience-criteria/<int:id>/edit', methods=['POST'])
@login_required
def edit_audience_criteria(id):
    ac = db.session.get(AudienceCriteria, id)
    if ac:
        ac.name = request.form.get('name', ac.name)
        ac.keywords = request.form.get('keywords', ac.keywords)
        ac.openai_prompt = request.form.get('openai_prompt', ac.openai_prompt)
        ac.min_confidence = float(request.form.get('min_confidence', ac.min_confidence))
        ac.active = 'active' in request.form
        db.session.commit()
        flash(f'Criteria "{ac.name}" updated.', 'success')
    return redirect(url_for('admin.audience_criteria'))


@admin_bp.route('/audience-criteria/<int:id>/delete', methods=['POST'])
@login_required
def delete_audience_criteria(id):
    ac = db.session.get(AudienceCriteria, id)
    if ac:
        db.session.delete(ac)
        db.session.commit()
        flash('Criteria deleted.', 'warning')
    return redirect(url_for('admin.audience_criteria'))


# ─── Module 2: Contacts ──────────────────────────────────────────────────────

@admin_bp.route('/contacts')
@login_required
def contacts():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    
    q = Contact.query

    if status_filter:
        q = q.filter_by(status=status_filter)
    
    if category_filter:
        q = q.filter_by(category=category_filter)

    contacts = q.order_by(Contact.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
    
    # Get statistics
    stats = {
        'total': Contact.query.count(),
        'target_audience': Contact.query.filter_by(category='target_audience').count(),
        'admin': Contact.query.filter_by(category='admin').count(),
        'competitor': Contact.query.filter_by(category='competitor').count(),
        'promoter': Contact.query.filter_by(category='promoter').count(),
        'bot': Contact.query.filter_by(category='bot').count(),
        'spam': Contact.query.filter_by(category='spam').count(),
    }
    
    return render_template('admin/contacts.html', 
                          contacts=contacts,
                          status_filter=status_filter,
                          category_filter=category_filter,
                          stats=stats)


# ─── Module 3: Templates ─────────────────────────────────────────────────────

@admin_bp.route('/templates', methods=['GET', 'POST'])
@login_required
def templates():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        body = request.form.get('body', '').strip()
        language = request.form.get('language', 'en')

        if name and body:
            tmpl = InvitationTemplate(name=name, body=body, language=language)
            db.session.add(tmpl)
            db.session.commit()
            flash(f'Template "{name}" added.', 'success')
        return redirect(url_for('admin.templates'))

    all_templates = InvitationTemplate.query.order_by(
        InvitationTemplate.created_at.desc()).all()
    return render_template('admin/templates.html', templates=all_templates)


@admin_bp.route('/templates/<int:id>/edit', methods=['POST'])
@login_required
def edit_template(id):
    tmpl = db.session.get(InvitationTemplate, id)
    if tmpl:
        tmpl.name = request.form.get('name', tmpl.name)
        tmpl.body = request.form.get('body', tmpl.body)
        tmpl.language = request.form.get('language', tmpl.language)
        tmpl.active = 'active' in request.form
        db.session.commit()
        flash(f'Template "{tmpl.name}" updated.', 'success')
    return redirect(url_for('admin.templates'))


@admin_bp.route('/templates/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_template(id):
    tmpl = db.session.get(InvitationTemplate, id)
    if tmpl:
        tmpl.active = not tmpl.active
        db.session.commit()
        flash(f'Template "{tmpl.name}" {"activated" if tmpl.active else "deactivated"}.', 'info')
    return redirect(url_for('admin.templates'))


@admin_bp.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    tmpl = db.session.get(InvitationTemplate, id)
    if tmpl:
        db.session.delete(tmpl)
        db.session.commit()
        flash('Template deleted.', 'warning')
    return redirect(url_for('admin.templates'))


# ─── Module 3: Invitation Log ────────────────────────────────────────────────

@admin_bp.route('/invitation-log')
@login_required
def invitation_log():
    page = request.args.get('page', 1, type=int)
    logs = InvitationLog.query.order_by(InvitationLog.sent_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
    return render_template('admin/invitation_log.html', logs=logs)


# ─── Module 4: Content Sources ───────────────────────────────────────────────

@admin_bp.route('/content-sources', methods=['GET', 'POST'])
@login_required
def content_sources():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        url = request.form.get('url', '').strip()
        source_type = request.form.get('source_type', 'rss')
        language = request.form.get('language', 'en')
        fetch_interval = int(request.form.get('fetch_interval_hours', 6))

        if name and url:
            src = ContentSource(
                name=name, url=url, source_type=source_type,
                language=language, fetch_interval_hours=fetch_interval
            )
            db.session.add(src)
            db.session.commit()
            flash(f'Source "{name}" added.', 'success')
        return redirect(url_for('admin.content_sources'))

    sources = ContentSource.query.order_by(ContentSource.created_at.desc()).all()
    return render_template('admin/content_sources.html', sources=sources)


@admin_bp.route('/content-sources/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_source(id):
    src = db.session.get(ContentSource, id)
    if src:
        src.active = not src.active
        db.session.commit()
        flash(f'Source "{src.name}" {"activated" if src.active else "deactivated"}.', 'info')
    return redirect(url_for('admin.content_sources'))


@admin_bp.route('/content-sources/<int:id>/delete', methods=['POST'])
@login_required
def delete_source(id):
    src = db.session.get(ContentSource, id)
    if src:
        db.session.delete(src)
        db.session.commit()
        flash('Source deleted.', 'warning')
    return redirect(url_for('admin.content_sources'))


# ─── Module 4: Published Posts ────────────────────────────────────────────────

@admin_bp.route('/published-posts', methods=['GET', 'POST'])
@login_required
def published_posts():
    if request.method == 'POST':
        # Create new post
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        channel = request.form.get('channel', AppConfig.get('target_channel', '')).strip()
        scheduled_at_str = request.form.get('scheduled_at', '')
        language = request.form.get('language', 'en')
        
        if not title or not content or not channel:
            flash('Title, content, and channel are required.', 'error')
            return redirect(url_for('admin.published_posts'))
        
        # Parse scheduled time if provided
        scheduled_at = None
        if scheduled_at_str:
            try:
                from datetime import datetime as dt
                scheduled_at = dt.fromisoformat(scheduled_at_str)
            except:
                pass
        
        # Create post record
        post = PublishedPost(
            source_title=title,
            rewritten_content=content,
            telegram_channel=channel,
            language=language,
            status='scheduled' if scheduled_at else 'published',
            scheduled_at=scheduled_at,
            published_at=None if scheduled_at else datetime.utcnow()
        )
        db.session.add(post)
        db.session.flush()  # Get the post ID
        
        # Handle media files (photos/videos)
        media_files = request.files.getlist('media_files')
        if media_files:
            import secrets
            for idx, file in enumerate(media_files):
                if file and file.filename:
                    # Save file
                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                    safe_filename = f"post_{post.id}_{secrets.token_hex(4)}.{ext}"
                    filepath = os.path.join('app/static/uploads', safe_filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)
                    
                    # Save media record
                    media_type = 'photo' if ext in ['jpg', 'jpeg', 'png', 'gif'] else 'video'
                    media = PostMedia(
                        published_post_id=post.id,
                        media_type=media_type,
                        file_path=safe_filename,
                        file_size=len(file.read()),
                        order=idx
                    )
                    file.seek(0)
                    db.session.add(media)
        
        db.session.commit()
        
        status_msg = 'scheduled' if scheduled_at else 'created'
        flash(f'Post {status_msg} successfully.', 'success')
        return redirect(url_for('admin.published_posts'))
    
    page = request.args.get('page', 1, type=int)
    posts = PublishedPost.query.order_by(PublishedPost.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
    
    target_channel = AppConfig.get('target_channel', '')
    return render_template('admin/published_posts.html', posts=posts, target_channel=target_channel)


# ─── Module 5: Paid Content ──────────────────────────────────────────────────

@admin_bp.route('/paid-content', methods=['GET', 'POST'])
@login_required
def paid_content():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '')
        content_type = request.form.get('content_type', 'photo')
        price_stars = int(request.form.get('price_stars', 1))
        category = request.form.get('category', '')
        language = request.form.get('language', 'en')

        file = request.files.get('file')
        file_path = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'paid')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join('paid', filename)
            file.save(os.path.join(upload_dir, filename))

        if title:
            pc = PaidContent(
                title=title, description=description, content_type=content_type,
                file_path=file_path, price_stars=price_stars,
                category=category, language=language
            )
            db.session.add(pc)
            db.session.commit()
            flash(f'Content "{title}" added.', 'success')
        return redirect(url_for('admin.paid_content'))

    items = PaidContent.query.order_by(PaidContent.created_at.desc()).all()
    return render_template('admin/paid_content.html', items=items)


@admin_bp.route('/paid-content/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_paid_content(id):
    pc = db.session.get(PaidContent, id)
    if pc:
        pc.active = not pc.active
        db.session.commit()
        flash(f'Content "{pc.title}" {"activated" if pc.active else "deactivated"}.', 'info')
    return redirect(url_for('admin.paid_content'))


@admin_bp.route('/paid-content/<int:id>/delete', methods=['POST'])
@login_required
def delete_paid_content(id):
    pc = db.session.get(PaidContent, id)
    if pc:
        # Delete file if exists
        if pc.file_path:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pc.file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
        db.session.delete(pc)
        db.session.commit()
        flash('Content deleted.', 'warning')
    return redirect(url_for('admin.paid_content'))


# ─── Module 5: Conversations ─────────────────────────────────────────────────

@admin_bp.route('/conversations')
@login_required
def conversations():
    page = request.args.get('page', 1, type=int)
    convs = Conversation.query.order_by(Conversation.last_message_at.desc().nullslast()).paginate(
        page=page, per_page=25, error_out=False)
    return render_template('admin/conversations.html', conversations=convs)


@admin_bp.route('/conversations/<int:id>')
@login_required
def conversation_detail(id):
    conv = db.session.get(Conversation, id)
    if not conv:
        flash('Conversation not found.', 'danger')
        return redirect(url_for('admin.conversations'))
    messages = ConversationMessage.query.filter_by(conversation_id=id).order_by(
        ConversationMessage.created_at.asc()).all()
    return render_template('admin/conversation_detail.html',
                           conversation=conv, messages=messages)


# ─── Module 5: Transactions ──────────────────────────────────────────────────

@admin_bp.route('/transactions')
@login_required
def transactions():
    page = request.args.get('page', 1, type=int)
    txns = StarTransaction.query.order_by(StarTransaction.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
    return render_template('admin/transactions.html', transactions=txns)


# ─── Settings: Chatbot Instructions ─────────────────────────────────────────

@admin_bp.route('/instructions', methods=['GET', 'POST'])
@login_required
def instructions():
    """Edit AI chatbot instructions for private messages and channel comments."""
    if request.method == 'POST':
        # Debug: Log what we received
        logger.info(f'instructions POST received. Form keys: {list(request.form.keys())}')
        logger.info(f'instructions POST csrf_token in form: {"csrf_token" in request.form}')
        
        action = request.form.get('action', '')
        logger.info(f'instructions: action="{action}"')
        
        # Default instructions
        default_dm = 'You are a helpful assistant for our Telegram channel. Be friendly, informative, and respond in the same language the user is using. Keep responses concise and engaging.'
        default_channel = 'You are responding to a paid comment in the Telegram channel. Provide expert, detailed responses that justify why the user paid for premium support. Be professional and thorough.'
        
        # Handle DM Instruction
        if action == 'save_dm':
            dm_instr = request.form.get('dm_instruction', '').strip()
            if dm_instr:
                AppConfig.set('openai_prompt_conversation', dm_instr,
                             'Instructions for AI responses to private messages')
                flash('DM instruction saved successfully.', 'success')
        elif action == 'reset_dm':
            AppConfig.set('openai_prompt_conversation', default_dm,
                         'Instructions for AI responses to private messages')
            flash('DM instruction reset to default.', 'info')
        
        # Handle Channel Instruction
        elif action == 'save_channel':
            channel_instr = request.form.get('channel_instruction', '').strip()
            if channel_instr:
                AppConfig.set('openai_prompt_channel_comments', channel_instr,
                             'Instructions for AI responses to paid channel comments')
                flash('Channel comment instruction saved successfully.', 'success')
        elif action == 'reset_channel':
            AppConfig.set('openai_prompt_channel_comments', default_channel,
                         'Instructions for AI responses to paid channel comments')
            flash('Channel comment instruction reset to default.', 'info')
        
        return redirect(url_for('admin.instructions'))
    
    # Get current instructions or defaults
    dm_instruction = AppConfig.get('openai_prompt_conversation',
        'You are a helpful assistant for our Telegram channel. Be friendly, informative, and respond in the same language the user is using. Keep responses concise and engaging.')
    
    channel_instruction = AppConfig.get('openai_prompt_channel_comments',
        'You are responding to a paid comment in the Telegram channel. Provide expert, detailed responses that justify why the user paid for premium support. Be professional and thorough.')
    
    # Get conversation stats for template
    conversation_stats = {
        'total': Conversation.query.count(),
        'active': Conversation.query.filter_by(status='active').count(),
        'messages_total': db.session.query(db.func.count(ConversationMessage.id)).scalar(),
    }
    
    return render_template('admin/instructions.html', 
                         dm_instruction=dm_instruction,
                         channel_instruction=channel_instruction,
                         conversation_stats=conversation_stats)


# ─── Settings: OpenAI ────────────────────────────────────────────────────────

@admin_bp.route('/openai-settings', methods=['GET', 'POST'])
@login_required
def openai_settings():
    if request.method == 'POST':
        modules = ['audience', 'publisher', 'conversation']
        for module in modules:
            prompt_key = f'openai_prompt_{module}'
            prompt_value = request.form.get(prompt_key, '')
            AppConfig.set(prompt_key, prompt_value, f'OpenAI system prompt for {module} module')

        model = request.form.get('openai_model', 'gpt-4o-mini')
        AppConfig.set('openai_model', model, 'OpenAI model to use')

        daily_budget = request.form.get('openai_daily_budget', '5.0')
        AppConfig.set('openai_daily_budget', daily_budget, 'Daily OpenAI budget in USD')

        flash('OpenAI settings saved.', 'success')
        return redirect(url_for('admin.openai_settings'))

    settings = {
        'openai_prompt_audience': AppConfig.get('openai_prompt_audience',
            'Analyze this Telegram user message and profile. Determine if they match our target audience. '
            'Respond with JSON: {"match": true/false, "confidence": 0.0-1.0, "reason": "..."}'),
        'openai_prompt_publisher': AppConfig.get('openai_prompt_publisher',
            'Rewrite this article for a Telegram channel. Make it engaging, concise, and add relevant emojis. '
            'Keep the key information but make it sound natural.'),
        'openai_prompt_conversation': AppConfig.get('openai_prompt_conversation',
            'You are a helpful assistant for our Telegram channel. Be friendly, informative, and helpful. '
            'Guide users towards our paid content when relevant.'),
        'openai_model': AppConfig.get('openai_model', 'gpt-4o-mini'),
        'openai_daily_budget': AppConfig.get('openai_daily_budget', '5.0'),
    }

    # Usage stats
    today = datetime.utcnow().date()
    today_usage = db.session.query(
        db.func.coalesce(db.func.sum(OpenAIUsageLog.total_tokens), 0),
        db.func.coalesce(db.func.sum(OpenAIUsageLog.cost_estimate), 0)
    ).filter(db.func.date(OpenAIUsageLog.created_at) == today).first()

    usage_stats = {
        'today_tokens': today_usage[0],
        'today_cost': today_usage[1],
        'total_tokens': db.session.query(
            db.func.coalesce(db.func.sum(OpenAIUsageLog.total_tokens), 0)).scalar(),
        'total_cost': db.session.query(
            db.func.coalesce(db.func.sum(OpenAIUsageLog.cost_estimate), 0)).scalar(),
    }

    return render_template('admin/openai_settings.html', settings=settings,
                           usage_stats=usage_stats)


# ─── Settings: Telegram Session ──────────────────────────────────────────────

@admin_bp.route('/telegram-session', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def telegram_session():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_credentials':
            api_id = request.form.get('api_id', '').strip()
            api_hash = request.form.get('api_hash', '').strip()
            phone = request.form.get('phone', '').strip()

            session = TelegramSession.query.filter_by(session_name='default').first()
            if not session:
                session = TelegramSession(session_name='default')
                db.session.add(session)

            if api_id:
                session.api_id = int(api_id)
            if api_hash:
                session.api_hash = api_hash
            if phone:
                session.phone_number = phone

            db.session.commit()
            flash('Telegram credentials saved.', 'success')

        elif action == 'save_session_string':
            session_string = request.form.get('session_string', '').strip()
            session = TelegramSession.query.filter_by(session_name='default').first()
            if session and session_string:
                session.session_string = session_string
                db.session.commit()
                flash('Session string saved.', 'success')

        return redirect(url_for('admin.telegram_session'))

    session = TelegramSession.query.filter_by(session_name='default').first()
    return render_template('admin/telegram_session.html', session=session)


# ─── Settings: General ───────────────────────────────────────────────────────

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        settings_map = {
            'target_channel': 'Target Telegram channel',
            'default_language': 'Default language for content',
            'discovery_interval_minutes': 'Minutes between discovery cycles',
            'audience_scan_interval_minutes': 'Minutes between audience scans',
            'invitation_min_delay_seconds': 'Min delay between invitations (seconds)',
            'invitation_max_delay_seconds': 'Max delay between invitations (seconds)',
            'max_invitations_per_day': 'Max invitations per day',
            'min_subscribers_filter': 'Min subscribers for channel filter',
            'publish_interval_hours': 'Hours between content publishing',
            'max_posts_per_day': 'Max posts per day',
        }
        for key, desc in settings_map.items():
            value = request.form.get(key, '')
            if value:
                AppConfig.set(key, value, desc)

        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))

    settings = {}
    defaults = {
        'target_channel': '@your_channel',
        'default_language': 'en',
        'discovery_interval_minutes': '30',
        'audience_scan_interval_minutes': '15',
        'invitation_min_delay_seconds': '60',
        'invitation_max_delay_seconds': '180',
        'max_invitations_per_day': '50',
        'min_subscribers_filter': '100',
        'publish_interval_hours': '4',
        'max_posts_per_day': '3',
    }
    for key, default in defaults.items():
        settings[key] = AppConfig.get(key, default)

    return render_template('admin/settings.html', settings=settings)


# ─── Business Goal & AI Keyword Generation ────────────────────────────────────

@admin_bp.route('/business-goal', methods=['GET', 'POST'])
@login_required
def business_goal():
    """Manage business goal and generate search keywords via AI."""
    from app.services.openai_service import get_openai_service
    
    try:
        if request.method == 'POST':
            logger.info(f'business_goal POST: form keys={list(request.form.keys())}')
            
            action = request.form.get('action', '')
            logger.info(f'business_goal: action="{action}"')
            
            if action == 'save_goal':
                goal_description = request.form.get('goal_description', '').strip()
                if not goal_description:
                    flash('Пожалуйста, опишите вашу бизнес-цель', 'warning')
                    return redirect(url_for('admin.business_goal'))
                
                AppConfig.set('business_goal', goal_description, 
                             'Business goal description for AI keyword generation')
                flash('Цель сохранена. Теперь генерируйте ключевые слова!', 'success')
                return redirect(url_for('admin.business_goal'))
            
            elif action == 'generate_keywords':
                goal_description = AppConfig.get('business_goal', '')
                if not goal_description:
                    flash('Сначала опишите вашу бизнес-цель', 'warning')
                    return redirect(url_for('admin.business_goal'))
                
                try:
                    # Generate keywords using OpenAI
                    openai_service = get_openai_service()
                    logger.info(f'OpenAI service obtained: {openai_service}')
                    
                    system_prompt = (
                        'You are an expert in Telegram channel discovery and marketing. '
                        'Generate a list of 15-25 specific, searchable keywords that will help find '
                        'Telegram channels and groups related to the given business goal. '
                        'Keywords should be in English, diverse, and practical for Telegram search. '
                        'Return ONLY comma-separated keywords, no explanations.'
                    )
                    
                    user_message = f'Business goal: {goal_description}'
                    logger.info(f'Calling OpenAI with: {user_message[:50]}...')
                    
                    result = openai_service.chat(
                        system_prompt=system_prompt,
                        user_message=user_message,
                        module='keyword_generation',
                    )
                    
                    logger.info(f'OpenAI result: {result}')
                    
                    if result.get('content'):
                        # Parse keywords from response
                        keywords_text = result['content'].strip()
                        keywords_list = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
                        
                        logger.info(f'Parsed {len(keywords_list)} keywords')
                        
                        # Clear old keywords and add new ones
                        SearchKeyword.query.delete()
                        
                        for i, keyword in enumerate(keywords_list, 1):
                            kw = SearchKeyword(
                                keyword=keyword,
                                language='en',
                                active=True,
                                priority=i,
                            )
                            db.session.add(kw)
                        
                        # CRITICAL: Set topic context for channel evaluation
                        # This allows discovery_service to intelligently filter channels
                        AppConfig.set('discovery_topic_context', goal_description,
                                     'Topic context for channel discovery evaluation')
                        
                        db.session.commit()
                        
                        flash(f'✓ Сгенерировано {len(keywords_list)} ключевых слов для поиска!', 'success')
                        logger.info(f'Generated {len(keywords_list)} keywords: {keywords_list[:5]}...')
                    else:
                        logger.error(f'No content in OpenAI result: {result}')
                        flash('Ошибка при генерации ключевых слов. Попробуйте снова.', 'danger')
                
                except Exception as e:
                    logger.exception(f'Error generating keywords: {e}')
                    flash(f'Ошибка: {str(e)[:100]}', 'danger')
                
                return redirect(url_for('admin.business_goal'))
        
        # GET request - show current goal and keywords
        business_goal = AppConfig.get('business_goal', '')
        logger.info(f'Loading business goal: {business_goal[:50] if business_goal else "None"}...')
        
        keywords = SearchKeyword.query.filter_by(active=True).order_by(
            SearchKeyword.priority
        ).all()
        logger.info(f'Loaded {len(keywords)} keywords')
        
        return render_template('admin/business_goal.html', 
                              business_goal=business_goal,
                              keywords=keywords)
    
    except Exception as e:
        logger.exception(f'Unexpected error in business_goal route: {e}')
        flash(f'Критическая ошибка: {str(e)[:100]}', 'danger')
        return redirect(url_for('admin.dashboard'))


# ─── Logs ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/logs')
@login_required
def logs():
    page = request.args.get('page', 1, type=int)
    task_type = request.args.get('type', '')

    q = TaskLog.query
    if task_type:
        q = q.filter_by(task_type=task_type)

    logs = q.order_by(TaskLog.started_at.desc()).paginate(
        page=page, per_page=50, error_out=False)
    return render_template('admin/logs.html', logs=logs, task_type=task_type)
