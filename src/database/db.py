from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Media(db.Model):
    __tablename__ = 'media'
    id = db.Column(db.Integer, primary_key=True)
    emby_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    media_type = db.Column(db.String(50), nullable=False)
    path = db.Column(db.Text)
    size = db.Column(db.BigInteger)
    duration = db.Column(db.Integer)
    year = db.Column(db.Integer)
    lib_id = db.Column(db.String(255), index=True)
    lib_name = db.Column(db.String(255), index=True)
    container = db.Column(db.String(50))
    video_codec = db.Column(db.String(50))
    audio_codec = db.Column(db.String(50))
    resolution = db.Column(db.String(20))
    bit_rate = db.Column(db.BigInteger)
    audio_channels = db.Column(db.Integer)
    audio_profile = db.Column(db.String(100))
    subtitle_langs = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Media {self.title}>"

class SyncLog(db.Model):
    __tablename__ = 'sync_logs'
    id = db.Column(db.Integer, primary_key=True)
    sync_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))
    items_synced = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f"<SyncLog {self.sync_time}>"
