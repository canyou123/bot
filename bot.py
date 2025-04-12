from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask
from youtube_utils import get_youtube_video_id, get_youtube_transcript, get_youtube_channel_id
from tiktok_utils import get_tiktok_video_id, analyze_tiktok_content
from facebook_utils import get_facebook_video_id, extract_facebook_content
from gpt_utils import summarize_transcript_with_g4f
import db_models
from channel_service import subscribe_to_channel, unsubscribe_from_channel, list_subscriptions, check_new_videos
from channel_utils import (
    get_youtube_recent_videos, get_tiktok_recent_videos, get_facebook_recent_videos,
    process_new_video
)

# Get token from environment variable
TOKEN = "7084946938:AAHe5HvIT7qy2BJi82oVkVZ9q9b8Mda5w04"

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Xin chào, {user.first_name}! 👋\n\n"
        f"Tôi là bot tóm tắt video YouTube. Để sử dụng, chỉ cần gửi cho tôi đường link video từ bất kỳ nền tảng nào trong số này.\n\n"
        f"📍 Sử dụng /help để xem hướng dẫn chi tiết."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    await update.message.reply_text(
        "🤖 *HƯỚNG DẪN SỬ DỤNG BOT TÓM TẮT VIDEO*\n\n"
        "1️⃣ Gửi link video YouTube, TikTok hoặc Facebook cần tóm tắt\n"
        "2️⃣ Bot sẽ tự động nhận diện loại video và xử lý\n"
        "3️⃣ Đối với YouTube: Bot sẽ trích xuất phụ đề (chủ yếu tiếng Việt)\n"
        "4️⃣ Bot sẽ tóm tắt nội dung\n"
        "5️⃣ Kết quả tóm tắt sẽ được gửi lại cho bạn\n\n"
        "*Tính năng theo dõi kênh:*\n"
        "- Đăng ký kênh để nhận thông báo khi có video mới\n"
        "- Tự động tóm tắt nội dung video mới\n\n"
        "*Lưu ý:*\n"
        "- Video YouTube phải có phụ đề tiếng Việt\n"
        "- Thời gian xử lý phụ thuộc vào độ dài nội dung\n\n"
        "*Các lệnh có sẵn:*\n"
        "/start - Khởi động bot\n"
        "/help - Xem hướng dẫn sử dụng\n"
        "/language [vi/en] - Thay đổi ngôn ngữ phụ đề (mặc định: Tiếng Việt)\n"
        "/subscribe [URL] - Đăng ký theo dõi kênh YouTube, TikTok hoặc Facebook\n"
        "/unsubscribe [URL] - Hủy đăng ký theo dõi kênh\n"
        "/list - Xem danh sách kênh đã đăng ký"
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set the language for transcript extraction."""
    if not context.args:
        await update.message.reply_text(
            "Vui lòng cung cấp mã ngôn ngữ. Ví dụ: /language en"
        )
        return
    
    language = context.args[0].lower()
    if language not in ["vi", "en"]:
        await update.message.reply_text(
            "Ngôn ngữ không được hỗ trợ. Hiện tại bot chỉ hỗ trợ: vi (Tiếng Việt) và en (Tiếng Anh)."
        )
        return
    
    # Store language preference in user data
    context.user_data["language"] = language
    
    lang_name = "Tiếng Việt" if language == "vi" else "English"
    await update.message.reply_text(f"Đã chuyển ngôn ngữ phụ đề sang {lang_name}.")

async def process_video_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process video URL (YouTube, TikTok, or Facebook) and handle subscriptions automatically."""
    url = update.message.text.strip()
    
    # Default language is Vietnamese
    language = context.user_data.get("language", "vi")
    
    # Check if the message contains a YouTube channel URL
    youtube_channel_id = get_youtube_channel_id(url)
    if youtube_channel_id:
        # Automatically subscribe to the channel
        processing_message = await update.message.reply_text(
            "⏳ Đang xử lý yêu cầu đăng ký kênh YouTube...\n"
            "Vui lòng đợi trong giây lát..."
        )
        
        success, message = subscribe_to_channel(update.effective_user, url)
        if success:
            await processing_message.edit_text(f"✅ {message}")
        else:
            await processing_message.edit_text(f"❌ {message}")
        return
    
    # Check if the message contains a YouTube video URL
    youtube_video_id = get_youtube_video_id(url)
    if youtube_video_id:
        await process_youtube_video(update, context, youtube_video_id, url, language)
        return
    
    # If not YouTube, check if it's a TikTok URL
    tiktok_id = get_tiktok_video_id(url)
    if tiktok_id:
        await process_tiktok_video(update, context, tiktok_id, url, language)
        return
        
    # If not YouTube or TikTok, check if it's a Facebook URL
    facebook_id = get_facebook_video_id(url)
    if facebook_id or 'facebook.com' in url or 'fb.watch' in url:
        await process_facebook_video(update, context, facebook_id, url, language)
        return
    
    # If neither YouTube, TikTok, nor Facebook, reply with an error message
    await update.message.reply_text(
        "❌ Link không hợp lệ."
    )

async def process_youtube_video(update: Update, context: ContextTypes.DEFAULT_TYPE, video_id: str, url: str, language: str) -> None:
    """Process YouTube video and return a summary."""
    # Send a processing message
    processing_message = await update.message.reply_text(
        "⏳ Đang xử lý video YouTube...\n"
        "🔍 Đang trích xuất phụ đề..."
    )
    
    # Get the transcript
    subtitles = get_youtube_transcript(video_id, language=language)
    
    if "Không tìm thấy phụ đề" in subtitles:
        await processing_message.edit_text(
            f"❌ {subtitles}\n\n"
            f"Thử sử dụng lệnh /language để chuyển ngôn ngữ phụ đề."
        )
        return
    
    # Update processing message
    await processing_message.edit_text(
        "✅ Đã trích xuất phụ đề thành công!\n"
        "🧠 Đang tóm tắt nội dung...\n"
        "⏳ Vui lòng đợi trong giây lát..."
    )
    
    # Get the summary
    summary = summarize_transcript_with_g4f(subtitles, language)
    
    if "Lỗi" in summary:
        await processing_message.edit_text(
            f"❌ {summary}\n\n"
            f"Vui lòng thử lại sau."
        )
        return
    
    # Send the summary
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    await processing_message.edit_text(
        f"📝 *TÓM TẮT VIDEO YOUTUBE*\n\n"
        f"🔗 *Link:* {video_url}\n\n"
        f"{summary}\n\n"
        
    )

async def process_tiktok_video(update: Update, context: ContextTypes.DEFAULT_TYPE, video_id: str, url: str, language: str) -> None:
    """Process TikTok video and return a summary."""
    # Send a processing message
    processing_message = await update.message.reply_text(
        "⏳ Đang xử lý video TikTok...\n"
        "🔍 Đang trích xuất nội dung..."
    )
    
    # Extract content from TikTok
    content = analyze_tiktok_content(url)
    
    if "Không thể" in content:
        await processing_message.edit_text(
            f"❌ {content}\n\n"
            f"Thử gửi một video TikTok khác."
        )
        return
    
    # Update processing message
    await processing_message.edit_text(
        "✅ Đã trích xuất nội dung thành công!\n"
        "🧠 Đang tóm tắt nội dung...\n"
        "⏳ Vui lòng đợi trong giây lát..."
    )
    
    # Get the summary
    summary = summarize_transcript_with_g4f(content, language)
    
    if "Lỗi" in summary:
        await processing_message.edit_text(
            f"❌ {summary}\n\n"
            f"Vui lòng thử lại sau."
        )
        return
    
    # Send the summary
    await processing_message.edit_text(
        f"📝 *TÓM TẮT VIDEO TIKTOK*\n\n"
        f"🔗 *Link:* {url}\n\n"
        f"{summary}\n\n"
        
    )

async def process_facebook_video(update: Update, context: ContextTypes.DEFAULT_TYPE, video_id: str | None, url: str, language: str) -> None:
    """Process Facebook video and return a summary."""
    # Send a processing message
    processing_message = await update.message.reply_text(
        "⏳ Đang xử lý video Facebook...\n"
        "🔍 Đang trích xuất nội dung và phụ đề..."
    )
    
    # Extract content from Facebook
    content = extract_facebook_content(url)
    
    if "Không thể" in content:
        await processing_message.edit_text(
            f"❌ {content}\n\n"
            f"Thử gửi một video Facebook khác hoặc đảm bảo video không bị giới hạn quyền riêng tư."
        )
        return
    
    # Update processing message
    await processing_message.edit_text(
        "✅ Đã trích xuất nội dung thành công!\n"
        "🧠 Đang tóm tắt nội dung...\n"
        "⏳ Vui lòng đợi trong giây lát..."
    )
    
    # Get the summary
    summary = summarize_transcript_with_g4f(content, language)
    
    if "Lỗi" in summary:
        await processing_message.edit_text(
            f"❌ {summary}\n\n"
            f"Vui lòng thử lại sau."
        )
        return
    
    # Send the summary
    await processing_message.edit_text(
        f"📝 *TÓM TẮT VIDEO FACEBOOK*\n\n"
        f"🔗 *Link:* {url}\n\n"
        f"{summary}\n\n"
    )

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Đăng ký theo dõi kênh YouTube, TikTok hoặc Facebook"""
    if not context.args:
        await update.message.reply_text(
            "Vui lòng cung cấp URL kênh YouTube, TikTok hoặc Facebook. Ví dụ: /subscribe https://www.youtube.com/channel/UC..."
        )
        return
    
    channel_url = context.args[0]
    
    # Gửi tin nhắn đang xử lý
    processing_message = await update.message.reply_text(
        "⏳ Đang xử lý yêu cầu đăng ký kênh...\n"
        "Vui lòng đợi trong giây lát..."
    )
    
    # Đăng ký kênh
    success, message = subscribe_to_channel(update.effective_user, channel_url)
    
    if success:
        await processing_message.edit_text(f"✅ {message}")
    else:
        await processing_message.edit_text(f"❌ {message}")

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hủy đăng ký theo dõi kênh"""
    if not context.args:
        await update.message.reply_text(
            "Vui lòng cung cấp URL kênh YouTube, TikTok hoặc Facebook đã đăng ký. Ví dụ: /unsubscribe https://www.youtube.com/channel/UC..."
        )
        return
    
    channel_url = context.args[0]
    
    # Gửi tin nhắn đang xử lý
    processing_message = await update.message.reply_text(
        "⏳ Đang xử lý yêu cầu hủy đăng ký...\n"
        "Vui lòng đợi trong giây lát..."
    )
    
    # Hủy đăng ký kênh
    success, message = unsubscribe_from_channel(update.effective_user, channel_url)
    
    if success:
        await processing_message.edit_text(f"✅ {message}")
    else:
        await processing_message.edit_text(f"❌ {message}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Liệt kê danh sách kênh đã đăng ký"""
    # Lấy danh sách đăng ký
    subscriptions = list_subscriptions(update.effective_user)
    
    if not subscriptions:
        await update.message.reply_text(
            "📋 Bạn chưa đăng ký theo dõi kênh nào."
        )
        return
    
    # Tạo danh sách hiển thị
    message = "📋 *DANH SÁCH KÊNH ĐÃ ĐĂNG KÝ*\n\n"
    
    for i, sub in enumerate(subscriptions, 1):
        if sub['platform'] == 'youtube':
            platform_icon = "🎬"
        elif sub['platform'] == 'tiktok':
            platform_icon = "📱"
        else:  # facebook
            platform_icon = "📺"
        channel_name = sub['channel_name'] or sub['channel_url']
        message += f"{i}. {platform_icon} *{channel_name}*\n"
        message += f"   🔗 {sub['channel_url']}\n\n"
    
    message += "Để hủy đăng ký, sử dụng lệnh: /unsubscribe [URL kênh]"
    
    await update.message.reply_text(message)

async def check_for_new_videos(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kiểm tra video mới từ các kênh đã đăng ký và gửi thông báo"""
    try:
        
        # Lấy danh sách kênh cần kiểm tra
        check_time = datetime.utcnow() - timedelta(minutes=30)
        channels = db_models.Channel.query.filter(
            db_models.Channel.last_checked < check_time
        ).order_by(db_models.Channel.last_checked.asc()).limit(10).all()
        
        
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
                    continue
                

                
                # Cập nhật thời gian kiểm tra
                channel.last_checked = datetime.utcnow()
                db_models.db.session.commit()
                
                # Kiểm tra từng video xem đã tồn tại trong cơ sở dữ liệu chưa
                for video_info in recent_videos:
                    video = db_models.Video.query.filter_by(
                        channel_id=channel.id, 
                        video_id=video_info['video_id']
                    ).first()
                    
                    if not video:
                        
                        # Video mới, thêm vào cơ sở dữ liệu
                        new_video = db_models.Video(
                            video_id=video_info['video_id'],
                            channel_id=channel.id,
                            title=video_info.get('title', 'Video mới'),
                            url=video_info['url'],
                            published_at=video_info.get('published_at', datetime.utcnow())
                        )
                        db_models.db.session.add(new_video)
                        db_models.db.session.commit()
                        
                        # Lấy danh sách người dùng đã đăng ký kênh này
                        subscriptions = db_models.Subscription.query.filter_by(channel_id=channel.id).all()
                        
                        # Xử lý video và tạo thông báo
                        for sub in subscriptions:
                            user = db_models.User.query.get(sub.user_id)
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
                                            db_models.db.session.commit()
                                        else:
                                            continue
                                    except Exception as e:
                                        continue
                                
                                # Gửi thông báo
                                try:
                                    message = (
                                        f"🎥 Video mới từ {channel.channel_name}!\n\n"
                                        f"📝 {new_video.title}\n"
                                        f"🔗 {new_video.url}\n"
                                    )
                                    if new_video.summary:
                                        message += f"\n📋 Tóm tắt:\n{new_video.summary}"
                                    
                                    await context.bot.send_message(
                                        chat_id=user.telegram_id,
                                        text=message,
                                        disable_web_page_preview=False
                                    )
                
                                except Exception as e:
                                    continue
                
            except Exception as e:
                # Vẫn cập nhật thời gian kiểm tra để tránh kiểm tra lỗi liên tục
                channel.last_checked = datetime.utcnow()
                db_models.db.session.commit()
        
    except Exception as e:
        1+1
def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Khởi tạo cơ sở dữ liệu cho Flask
    app = Flask(__name__)
    app.app_context().push()  # Push the context
    
    # Cấu hình và khởi tạo cơ sở dữ liệu
    db_models.init_app(app)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("language", set_language))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("list", list_command))

    # Add message handler for video URLs (YouTube, TikTok and Facebook)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        process_video_url
    ))
    
    # Thêm tác vụ kiểm tra video mới định kỳ (mỗi 5 phút)
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(check_for_new_videos, interval=300, first=10)

    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    if TOKEN:
        main()
