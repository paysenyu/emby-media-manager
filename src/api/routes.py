import os
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from src.database.db import db, Media, SyncLog
from src.emby.client import EmbyClient
from src.emby.sync import EmbySyncService

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

def get_emby_client():
    return EmbyClient(
        os.getenv('EMBY_SERVER_URL', 'http://localhost:8096'),
        os.getenv('EMBY_API_KEY', '')
    )

@api_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0',
                    'timestamp': datetime.now(timezone.utc).isoformat()})

@api_bp.route('/emby/test-connection')
def test_connection():
    try:
        client = get_emby_client()
        ok = client.test_connection()
        return jsonify({'connected': ok, 'server_url': os.getenv('EMBY_SERVER_URL', '')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/emby/libraries')
def get_libraries():
    try:
        libs = get_emby_client().get_libraries()
        return jsonify({'libraries': libs, 'count': len(libs)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/emby/sync', methods=['POST'])
def trigger_sync():
    try:
        EmbySyncService().sync_all_libraries()
        return jsonify({'message': 'Sync completed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/media')
def get_media():
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        media_type = request.args.get('type')
        query = Media.query
        if media_type:
            query = query.filter_by(media_type=media_type)
        p = query.order_by(Media.title).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'items': [{'id': m.id, 'emby_id': m.emby_id, 'title': m.title,
                       'media_type': m.media_type, 'year': m.year, 'path': m.path,
                       'size': m.size, 'duration': m.duration,
                       'created_at': m.created_at.isoformat() if m.created_at else None}
                      for m in p.items],
            'total': p.total, 'page': page, 'per_page': per_page, 'pages': p.pages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/media/<emby_id>')
def get_media_item(emby_id):
    try:
        m = Media.query.filter_by(emby_id=emby_id).first()
        if not m:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({'id': m.id, 'emby_id': m.emby_id, 'title': m.title,
                        'media_type': m.media_type, 'year': m.year, 'path': m.path,
                        'size': m.size, 'duration': m.duration,
                        'created_at': m.created_at.isoformat() if m.created_at else None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/sync/logs')
def get_sync_logs():
    try:
        logs = SyncLog.query.order_by(SyncLog.sync_time.desc()).limit(50).all()
        return jsonify({'logs': [{'id': l.id,
            'sync_time': l.sync_time.isoformat() if l.sync_time else None,
            'status': l.status, 'items_synced': l.items_synced,
            'error_message': l.error_message} for l in logs]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
