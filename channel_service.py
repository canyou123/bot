import re
import logging
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from db_models import db, User, Channel, Video, Subscription
from channel_utils import (
    extract_youtube_channel_id, extract_tiktok_username, extract_facebook_page_id,
    get_youtube_channel_info, get_tiktok_channel_info, get_facebook_page_info,
    get_youtube_recent_videos, get_tiktok_recent_videos, get_facebook_recent_videos,
    process_new_video
)

# Thiết lập logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def identify_channel_type(channel_url):
    """Xác định loại kênh (YouTube, TikTok hoặc Facebook) từ URL"""
    if re.search(r'youtube\.com|youtu\.be', channel_url, re.IGNORECASE):
        return 'youtube'
    elif re.search(r'tiktok\.com', channel_url, re.IGNORECASE):
        return 'tiktok'
    elif re.search(r'facebook\.com|fb\.com|fb\.watch', channel_url, re.IGNORECASE):
        return 'facebook'
    else:
        return None

def get_or_create_user(telegram_user):
    """Lấy hoặc tạo user trong cơ sở dữ liệu từ thông tin người dùng Telegram"""
    if not telegram_user:
        return None
    
    user = User.query.filter_by(telegram_id=telegram_user.id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            user = User.query.filter_by(telegram_id=telegram_user.id).first()
    
    return user

def subscribe_to_channel(telegram_user, channel_url):
    """Đăng ký theo dõi kênh"""
    # Tạo và sử dụng ngữ cảnh Flask để làm việc với cơ sở dữ liệu
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        # Khởi tạo cơ sở dữ liệu
        import db_models
        db_models.init_app(app)
        
        user = get_or_create_user(telegram_user)
        if not user:
            return False, "Không thể tạo người dùng"
        
        # Xác định loại kênh (YouTube, TikTok hoặc Facebook)
        platform = identify_channel_type(channel_url)
        if not platform:
            return False, "URL không hợp lệ. Vui lòng nhập URL kênh YouTube, TikTok hoặc Facebook."
        
        try:
            # Xử lý theo loại kênh
            if platform == 'youtube':
                channel_id = extract_youtube_channel_id(channel_url)
                if not channel_id:
                    return False, "Không thể xác định ID kênh YouTube từ URL đã cung cấp."
                
                result = get_youtube_channel_info(channel_id)
                if result[0] is None:
                    return False, f"Không thể lấy thông tin kênh YouTube: {channel_url}"
                channel_id, channel_name, channel_url = result
            elif platform == 'tiktok':
                username = extract_tiktok_username(channel_url)
                if not username:
                    return False, "Không thể xác định username TikTok từ URL đã cung cấp."
                
                result = get_tiktok_channel_info(username)
                if result[0] is None:
                    return False, f"Không thể lấy thông tin kênh TikTok: {channel_url}"
                channel_id, channel_name, channel_url = result
            else:  # platform == 'facebook'
                page_id = extract_facebook_page_id(channel_url)
                if not page_id:
                    return False, "Không thể xác định ID trang Facebook từ URL đã cung cấp."
                
                result = get_facebook_page_info(page_id)
                if result[0] is None:
                    return False, f"Không thể lấy thông tin kênh Facebook: {channel_url}"
                channel_id, channel_name, channel_url = result
            
            if not channel_id:
                return False, f"Không thể lấy thông tin kênh từ URL: {channel_url}"
            
            # Kiểm tra xem kênh đã tồn tại trong cơ sở dữ liệu chưa
            channel = Channel.query.filter_by(platform=platform, channel_id=channel_id).first()
            
            if not channel:
                # Tạo kênh mới
                channel = Channel(
                    platform=platform,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    channel_url=channel_url
                )
                db.session.add(channel)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    channel = Channel.query.filter_by(platform=platform, channel_id=channel_id).first()
            
            # Kiểm tra xem người dùng đã đăng ký kênh này chưa
            subscription = Subscription.query.filter_by(user_id=user.id, channel_id=channel.id).first()
            if subscription:
                return False, f"Bạn đã đăng ký kênh {channel.channel_name or channel.channel_url} rồi."
            
            # Tạo đăng ký mới
            subscription = Subscription(user_id=user.id, channel_id=channel.id)
            db.session.add(subscription)
            
            try:
                db.session.commit()
                return True, f"Đã đăng ký theo dõi kênh: {channel.channel_name or channel.channel_url}"
            except IntegrityError:
                db.session.rollback()
                return False, "Đã xảy ra lỗi khi đăng ký kênh."
        except Exception as e:
            import logging
            logging.error(f"Lỗi khi đăng ký kênh: {str(e)}")
            return False, f"Đã xảy ra lỗi khi đăng ký kênh: {str(e)}"

def unsubscribe_from_channel(telegram_user, channel_url):
    """Hủy đăng ký theo dõi kênh"""
    # Tạo và sử dụng ngữ cảnh Flask để làm việc với cơ sở dữ liệu
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        # Khởi tạo cơ sở dữ liệu
        import db_models
        db_models.init_app(app)
        
        user = User.query.filter_by(telegram_id=telegram_user.id).first()
        if not user:
            return False, "Bạn chưa đăng ký bất kỳ kênh nào."
        
        # Xác định loại kênh (YouTube, TikTok hoặc Facebook)
        platform = identify_channel_type(channel_url)
        if not platform:
            return False, "URL không hợp lệ. Vui lòng nhập URL kênh YouTube, TikTok hoặc Facebook."
        
        try:
            # Xử lý theo loại kênh
            if platform == 'youtube':
                channel_id = extract_youtube_channel_id(channel_url)
            elif platform == 'tiktok':
                channel_id = extract_tiktok_username(channel_url)
            else:  # platform == 'facebook'
                channel_id = extract_facebook_page_id(channel_url)
            
            if not channel_id:
                return False, f"Không thể xác định ID kênh từ URL: {channel_url}"
            
            # Tìm kênh trong cơ sở dữ liệu
            channel = Channel.query.filter_by(platform=platform, channel_id=channel_id).first()
            if not channel:
                return False, "Bạn chưa đăng ký kênh này."
            
            # Tìm đăng ký
            subscription = Subscription.query.filter_by(user_id=user.id, channel_id=channel.id).first()
            if not subscription:
                return False, "Bạn chưa đăng ký kênh này."
            
            # Xóa đăng ký
            db.session.delete(subscription)
            
            try:
                db.session.commit()
                return True, f"Đã hủy đăng ký kênh: {channel.channel_name or channel.channel_url}"
            except Exception as e:
                db.session.rollback()
                return False, f"Đã xảy ra lỗi khi hủy đăng ký kênh: {str(e)}"
        except Exception as e:
            import logging
            logging.error(f"Lỗi khi hủy đăng ký kênh: {str(e)}")
            return False, f"Đã xảy ra lỗi khi hủy đăng ký kênh: {str(e)}"

def list_subscriptions(telegram_user):
    """Liệt kê danh sách kênh đã đăng ký"""
    # Tạo và sử dụng ngữ cảnh Flask để làm việc với cơ sở dữ liệu
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        # Khởi tạo cơ sở dữ liệu
        import db_models
        db_models.init_app(app)
        
        try:
            user = User.query.filter_by(telegram_id=telegram_user.id).first()
            if not user:
                return []
            
            # Lấy danh sách đăng ký với thông tin kênh
            subscriptions = Subscription.query.filter_by(user_id=user.id).all()
            
            result = []
            for sub in subscriptions:
                channel = sub.channel
                result.append({
                    'id': channel.id,
                    'platform': channel.platform,
                    'channel_id': channel.channel_id,
                    'channel_name': channel.channel_name,
                    'channel_url': channel.channel_url
                })
            
            return result
        except Exception as e:
            import logging
            logging.error(f"Lỗi khi liệt kê danh sách đăng ký: {str(e)}")
            return []

def check_new_videos(limit=10):
    """
    Kiểm tra video mới từ tất cả các kênh đã đăng ký
    
    Args:
        limit (int): Số kênh tối đa để kiểm tra trong một lần chạy
        
    Returns:
        list: Danh sách thông báo để gửi đi
    """
    try:
        # Lấy các kênh đã được kiểm tra cách đây ít nhất 30 phút
        check_time = datetime.utcnow() - timedelta(minutes=30)
        channels = Channel.query.filter(
            Channel.last_checked < check_time
        ).order_by(Channel.last_checked.asc()).limit(limit).all()
        
        notifications = []
        
        for channel in channels:
            try:
                # Lấy danh sách video mới nhất từ kênh
                if channel.platform == 'youtube':
                    recent_videos = get_youtube_recent_videos(channel.channel_id, max_results=5)
                elif channel.platform == 'tiktok':
                    recent_videos = get_tiktok_recent_videos(channel.channel_id, max_results=5)
                else:  # platform == 'facebook'
                    recent_videos = get_facebook_recent_videos(channel.channel_id, max_results=5)
                
                if not recent_videos:
                    logger.warning(f"Không tìm thấy video mới từ kênh {channel.channel_id}")
                    continue
                
                # Cập nhật thời gian kiểm tra
                channel.last_checked = datetime.utcnow()
                db.session.commit()
                
                # Kiểm tra từng video xem đã tồn tại trong cơ sở dữ liệu chưa
                for video_info in recent_videos:
                    video = Video.query.filter_by(
                        channel_id=channel.id, 
                        video_id=video_info['video_id']
                    ).first()
                    
                    if not video:
                        # Video mới, thêm vào cơ sở dữ liệu
                        new_video = Video(
                            video_id=video_info['video_id'],
                            channel_id=channel.id,
                            title=video_info.get('title', 'Video mới'),
                            url=video_info['url'],
                            published_at=video_info.get('published_at', datetime.utcnow())
                        )
                        db.session.add(new_video)
                        db.session.commit()
                        
                        # Lấy danh sách người dùng đã đăng ký kênh này
                        subscriptions = Subscription.query.filter_by(channel_id=channel.id).all()
                        
                        # Xử lý video và tạo thông báo
                        for sub in subscriptions:
                            user = User.query.get(sub.user_id)
                            if user:
                                # Lấy tóm tắt nội dung nếu chưa xử lý
                                if not new_video.processed:
                                    try:
                                        summary = process_new_video(
                                            channel.platform, 
                                            video_info, 
                                            language=user.language or 'vi'
                                        )
                                        if summary:
                                            new_video.summary = summary
                                            new_video.processed = True
                                            db.session.commit()
                                            logger.info(f"Đã tóm tắt video {video_info['video_id']}")
                                        else:
                                            logger.warning(f"Không thể tóm tắt video {video_info['video_id']}")
                                    except Exception as e:
                                        logger.error(f"Lỗi khi tóm tắt video {video_info['video_id']}: {str(e)}")
                                
                                # Tạo thông báo
                                notifications.append({
                                    'telegram_id': user.telegram_id,
                                    'platform': channel.platform,
                                    'channel_name': channel.channel_name or channel.channel_url,
                                    'video_title': new_video.title,
                                    'video_url': new_video.url,
                                    'summary': new_video.summary
                                })
                                logger.info(f"Đã tạo thông báo cho user {user.telegram_id}")
            
            except Exception as e:
                logger.error(f"Lỗi khi kiểm tra video mới từ kênh {channel.channel_id}: {str(e)}")
                # Vẫn cập nhật thời gian kiểm tra để tránh kiểm tra lỗi liên tục
                channel.last_checked = datetime.utcnow()
                db.session.commit()
        
        return notifications
        
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra video mới: {str(e)}")
        return []