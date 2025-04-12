from flask import Flask
from db_models import db, Channel, Subscription, Video, User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db.init_app(app)

with app.app_context():
    # Kiểm tra kênh
    channel = Channel.query.filter_by(channel_id='hoasen6669').first()
    if channel:
        logger.info(f"Tìm thấy kênh: {channel.channel_name} (ID: {channel.channel_id})")
        logger.info(f"Platform: {channel.platform}")
        logger.info(f"Last checked: {channel.last_checked}")
        
        # Kiểm tra đăng ký
        subs = Subscription.query.filter_by(channel_id=channel.id).all()
        logger.info(f"Số lượng người đăng ký: {len(subs)}")
        for sub in subs:
            user = User.query.get(sub.user_id)
            logger.info(f"User: {user.telegram_id}")
            
        # Kiểm tra video
        videos = Video.query.filter_by(channel_id=channel.id).all()
        logger.info(f"Số lượng video: {len(videos)}")
        for video in videos:
            logger.info(f"Video {video.video_id}: {video.title} ({video.published_at})")
    else:
        logger.error("Không tìm thấy kênh trong database")
