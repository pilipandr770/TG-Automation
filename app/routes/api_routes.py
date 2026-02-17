import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, Response
from flask_login import login_required
from app import db
from app.models import (
    DiscoveredChannel, Contact, InvitationLog, PublishedPost,
    StarTransaction, Conversation, TaskLog, OpenAIUsageLog,
    SearchKeyword, AppConfig
)

api_bp = Blueprint('api', __name__)


@api_bp.route('/stats')
@login_required
def stats():
    """Dashboard stats for AJAX refresh."""
    stats = {
        'channels_found': DiscoveredChannel.query.count(),
        'channels_joined': DiscoveredChannel.query.filter_by(is_joined=True).count(),
        'contacts_total': Contact.query.count(),
        'contacts_invited': Contact.query.filter_by(invitation_sent=True).count(),
        'invitations_sent': InvitationLog.query.count(),
        'invitations_failed': InvitationLog.query.filter_by(status='failed').count(),
        'posts_published': PublishedPost.query.filter_by(status='published').count(),
        'conversations_active': Conversation.query.filter_by(status='active').count(),
        'total_stars': db.session.query(
            db.func.coalesce(db.func.sum(StarTransaction.amount_stars), 0)).scalar(),
    }

    # Today's stats
    today = datetime.utcnow().date()
    stats['contacts_today'] = Contact.query.filter(
        db.func.date(Contact.created_at) == today).count()
    stats['invitations_today'] = InvitationLog.query.filter(
        db.func.date(InvitationLog.sent_at) == today).count()
    stats['posts_today'] = PublishedPost.query.filter(
        db.func.date(PublishedPost.published_at) == today).count()

    return jsonify(stats)


@api_bp.route('/worker-status')
@login_required
def worker_status():
    """Check Telethon worker health via Redis heartbeat."""
    try:
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            return jsonify({'status': 'unknown', 'message': 'Redis not configured'})

        import redis
        r = redis.from_url(redis_url)
        heartbeat = r.get('telethon_worker_heartbeat')

        if heartbeat:
            last_beat = datetime.fromisoformat(heartbeat.decode())
            age_seconds = (datetime.utcnow() - last_beat).total_seconds()
            if age_seconds < 120:
                return jsonify({
                    'status': 'running',
                    'last_heartbeat': heartbeat.decode(),
                    'age_seconds': int(age_seconds)
                })
            else:
                return jsonify({
                    'status': 'stale',
                    'last_heartbeat': heartbeat.decode(),
                    'age_seconds': int(age_seconds),
                    'message': 'Worker heartbeat is stale (>2 min)'
                })
        else:
            return jsonify({'status': 'offline', 'message': 'No heartbeat found'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@api_bp.route('/discovery/trigger', methods=['POST'])
@login_required
def trigger_discovery():
    """Trigger immediate discovery cycle via Redis command."""
    try:
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            return jsonify({'error': 'Redis not configured'}), 503

        import redis
        r = redis.from_url(redis_url)
        r.publish('telethon_commands', json.dumps({
            'action': 'run_discovery',
            'timestamp': datetime.utcnow().isoformat()
        }))
        return jsonify({'status': 'triggered', 'message': 'Discovery cycle triggered'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/invitations/trigger', methods=['POST'])
@login_required
def trigger_invitations():
    """Trigger immediate invitation batch via Redis command."""
    try:
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            return jsonify({'error': 'Redis not configured'}), 503

        import redis
        r = redis.from_url(redis_url)
        r.publish('telethon_commands', json.dumps({
            'action': 'run_invitations',
            'limit': request.json.get('limit', 10) if request.is_json else 10,
            'timestamp': datetime.utcnow().isoformat()
        }))
        return jsonify({'status': 'triggered', 'message': 'Invitation batch triggered'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/publish/trigger', methods=['POST'])
@login_required
def trigger_publish():
    """Trigger immediate publish cycle via Redis command."""
    try:
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            return jsonify({'error': 'Redis not configured'}), 503

        import redis
        r = redis.from_url(redis_url)
        r.publish('telethon_commands', json.dumps({
            'action': 'run_publisher',
            'max_posts': request.json.get('max_posts', 3) if request.is_json else 3,
            'timestamp': datetime.utcnow().isoformat()
        }))
        return jsonify({'status': 'triggered', 'message': 'Publisher cycle triggered'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/contacts/export')
@login_required
def export_contacts():
    """Export contacts as CSV."""
    import csv
    import io

    contacts = Contact.query.order_by(Contact.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'telegram_id', 'username', 'first_name', 'last_name',
        'confidence_score', 'status', 'invitation_sent', 'created_at'
    ])

    for c in contacts:
        writer.writerow([
            c.telegram_id, c.username or '', c.first_name or '', c.last_name or '',
            c.confidence_score, c.status, c.invitation_sent,
            c.created_at.isoformat() if c.created_at else ''
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=contacts_{datetime.utcnow().strftime("%Y%m%d")}.csv'}
    )


@api_bp.route('/channels/<int:id>/details')
@login_required
def channel_details(id):
    """Channel detail for modal popup."""
    ch = db.session.get(DiscoveredChannel, id)
    if not ch:
        return jsonify({'error': 'Not found'}), 404

    return jsonify({
        'id': ch.id,
        'telegram_id': ch.telegram_id,
        'username': ch.username,
        'title': ch.title,
        'description': ch.description,
        'channel_type': ch.channel_type,
        'subscriber_count': ch.subscriber_count,
        'has_comments': ch.has_comments,
        'is_joined': ch.is_joined,
        'is_blacklisted': ch.is_blacklisted,
        'topic_match_score': ch.topic_match_score,
        'status': ch.status,
        'created_at': ch.created_at.isoformat() if ch.created_at else None,
        'contacts_found': Contact.query.filter_by(source_channel_id=ch.id).count()
    })
