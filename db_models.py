import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """Telegram user information"""
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(10), default='vi')
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.telegram_id}>'

class Channel(db.Model):
    """YouTube or TikTok channel information"""
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(20), nullable=False)  # 'youtube' or 'tiktok'
    channel_id = db.Column(db.String(255), nullable=False)
    channel_name = db.Column(db.String(255), nullable=True)
    channel_url = db.Column(db.String(512), nullable=False)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())
    
    # Relationships
    videos = db.relationship('Video', backref='channel', lazy=True, cascade="all, delete-orphan")
    subscriptions = db.relationship('Subscription', backref='channel', lazy=True, cascade="all, delete-orphan")
    
    __table_args__ = (
        db.UniqueConstraint('platform', 'channel_id', name='_platform_channel_id_uc'),
    )
    
    def __repr__(self):
        return f'<Channel {self.platform}:{self.channel_id}>'

class Video(db.Model):
    """Video information from the channel"""
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(255), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    title = db.Column(db.String(512), nullable=True)
    url = db.Column(db.String(512), nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())
    
    __table_args__ = (
        db.UniqueConstraint('channel_id', 'video_id', name='_channel_video_id_uc'),
    )
    
    def __repr__(self):
        return f'<Video {self.video_id}>'

class Subscription(db.Model):
    """User subscription to channel"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'channel_id', name='_user_channel_uc'),
    )
    
    def __repr__(self):
        return f'<Subscription user_id={self.user_id} channel_id={self.channel_id}>'

def init_app(app):
    """Initialize the database with the Flask app"""
    # Ưu tiên sử dụng SQLite thay vì PostgreSQL
    sqlite_path = 'sqlite:///database.db'
    db_url = os.environ.get('DATABASE_URL', sqlite_path)
    
    # Nếu muốn dùng SQLite, bỏ qua PostgreSQL mặc dù đã có biến môi trường
    if os.environ.get('USE_SQLITE', 'True').lower() in ('true', '1', 't'):
        db_url = sqlite_path
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    # Create tables
    with app.app_context():
        db.create_all()