import re
import requests
from bs4 import BeautifulSoup
import logging
from yt_dlp import YoutubeDL
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import os
from telegram import Update
from telegram.ext import ContextTypes

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_facebook_video_id(url):
    """
    Trích xuất ID video Facebook từ URL
    
    Args:
        url (str): Đường link video Facebook
        
    Returns:
        str: ID video Facebook nếu tìm thấy, None nếu không
    """
    # Pattern cho video Facebook
    patterns = [
        r'facebook\.com\/(.+?)\/videos\/(\d+)', # facebook.com/page/videos/id
        r'facebook\.com\/watch\/\?v=(\d+)',     # facebook.com/watch/?v=id
        r'fb\.watch\/(.+?)\/(\d+)',             # fb.watch/path/id
        r'facebook\.com\/watch\?v=(\d+)'        # facebook.com/watch?v=id
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match and match.lastindex is not None:
            # Trả về group cuối cùng đã match, đó là ID video
            groups = match.groups()
            return groups[-1] if groups else None
    
    return None

def extract_facebook_content(url: str) -> str:
    """
    Extract content (title, description, and subtitles) from a Facebook video using Selenium and BeautifulSoup.
    """
    try:
        # Configure Selenium WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        service = Service("C:\\Users\\PC\\OneDrive\\Máy tính\\Dự án chatbot\\chromedriver-win64\\chromedriver.exe")  # Replace with the path to your ChromeDriver
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Open the Facebook video URL
        driver.get(url)
        time.sleep(5)  # Wait for the page to load

        # Get the page source
        page_source = driver.page_source
        driver.quit()

        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(page_source, "html.parser")

        # Extract title and description
        title = soup.find("meta", property="og:title")
        description = soup.find("meta", property="og:description")
        title_text = title["content"] if title else "Không có tiêu đề"
        description_text = description["content"] if description else "Không có mô tả"

        # Find subtitles URL
        subtitles_url = None
        for script in soup.find_all("script"):
            if ".vtt" in script.text or ".srt" in script.text:
                start_index = script.text.find("https://")
                end_index = script.text.find(".vtt") + 4 if ".vtt" in script.text else script.text.find(".srt") + 4
                subtitles_url = script.text[start_index:end_index]
                break

        # Download subtitles if available
        subtitles_file_path = ""
        if subtitles_url:
            subtitles_file_path = download_facebook_subtitles(subtitles_url)

        # Combine content
        content = f"Tiêu đề: {title_text}\n\nMô tả: {description_text}\n\n"
        if subtitles_file_path:
            content += f"Phụ đề đã được tải xuống: {subtitles_file_path}"
        else:
            content += "Không tìm thấy phụ đề."

        return content.strip()

    except Exception as e:
        return f"Không thể trích xuất nội dung video Facebook. Lỗi: {str(e)}"

def download_facebook_subtitles(subtitles_url: str, output_dir: str = "subtitles") -> str:
    """
    Download subtitles from a given URL and save it as a file.

    Args:
        subtitles_url (str): URL of the subtitles file (.vtt or .srt).
        output_dir (str): Directory to save the subtitles file.

    Returns:
        str: Path to the saved subtitles file.
    """
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Determine the file extension
        file_extension = ".vtt" if ".vtt" in subtitles_url else ".srt"
        file_name = f"facebook_subtitles{file_extension}"
        file_path = os.path.join(output_dir, file_name)

        # Download the subtitles
        response = requests.get(subtitles_url)
        if response.status_code == 200:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(response.text)
            return file_path
        else:
            raise Exception(f"Failed to download subtitles. HTTP status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error downloading subtitles: {str(e)}")
        return ""

async def process_facebook_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
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
    
    # Send the content
    await processing_message.edit_text(content)
    
    # Check if subtitles were downloaded
    if "Phụ đề đã được tải xuống:" in content:
        subtitles_path = content.split("Phụ đề đã được tải xuống: ")[-1]
        try:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(subtitles_path, "rb"),
                caption="🎥 Đây là file phụ đề của video bạn yêu cầu."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Không thể gửi file phụ đề. Lỗi: {str(e)}")