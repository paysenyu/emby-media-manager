from datetime import datetime
from src.database.db import db, Media, SyncLog  # re-export
__all__ = ['Media', 'SyncLog', 'DedupRule', 'UpgradeTask', 'OperationLog']

class DedupRule(db.Model):
    __tablename__ = 'dedup_rules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    rule_type = db.Column(db.String(50), nullable=False)
    config_json = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UpgradeTask(db.Model):
    __tablename__ = 'upgrade_tasks'
    id = db.Column(db.Integer, primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')
    source_path = db.Column(db.Text)
    target_path = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    media = db.relationship('Media', backref='upgrade_tasks')

class OperationLog(db.Model):
    __tablename__ = 'operation_logs'
    id = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.String(255))
    target_type = db.Column(db.String(50))
    detail = db.Column(db.Text)
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
