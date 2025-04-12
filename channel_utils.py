import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
from youtube_utils import get_youtube_video_id, get_youtube_transcript
from tiktok_utils import get_tiktok_video_id, analyze_tiktok_content
from facebook_utils import get_facebook_video_id, extract_facebook_content
from gpt_utils import summarize_transcript_with_g4f

# Thiết lập logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_youtube_channel_id(url):
    """
    Trích xuất ID kênh YouTube từ URL
    
    Hỗ trợ các định dạng:
    - youtube.com/channel/UC...
    - youtube.com/c/ChannelName
    - youtube.com/user/Username
    - youtube.com/@username
    """
    if not url:
        return None
    
    # Xử lý URL kênh trực tiếp
    channel_pattern = r'youtube\.com/channel/(UC[\w-]+)'
    match = re.search(channel_pattern, url)
    if match:
        return match.group(1)
    
    # Xử lý URL kênh tùy chỉnh hoặc URL @username
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Tìm thẻ meta với property="og:url"
            meta_tag = soup.find('meta', property='og:url')
            if meta_tag:
                channel_url = meta_tag.get('content', '')
                match = re.search(channel_pattern, channel_url)
                if match:
                    return match.group(1)
            
            # Tìm trong nội dung trang
            channel_id_matches = re.findall(r'"channelId":"(UC[\w-]+)"', response.text)
            if channel_id_matches:
                return channel_id_matches[0]
        
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất ID kênh YouTube: {e}")
    
    return None

def extract_tiktok_username(url):
    """
    Trích xuất username TikTok từ URL
    
    Hỗ trợ các định dạng:
    - tiktok.com/@username
    """
    if not url:
        return None
    
    # Mẫu cho username TikTok
    username_pattern = r'tiktok\.com/@([\w.]+)'
    match = re.search(username_pattern, url)
    if match:
        return match.group(1)
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Tìm thẻ canonical
            canonical = soup.find('link', rel='canonical')
            if canonical:
                href = canonical.get('href', '')
                match = re.search(username_pattern, href)
                if match:
                    return match.group(1)
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất username TikTok: {e}")
    
    return None

def extract_facebook_page_id(url):
    """
    Trích xuất ID trang Facebook từ URL
    
    Hỗ trợ các định dạng:
    - facebook.com/pagename
    - facebook.com/profile.php?id=ID
    - facebook.com/pages/NAME/ID
    - fb.com/pagename
    """
    if not url:
        return None
    
    # Loại bỏ query parameters (trừ trường hợp profile.php?id=)
    if "profile.php?id=" in url:
        pattern = r'facebook\.com/profile\.php\?id=(\d+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    else:
        # Loại bỏ query parameters
        url = url.split('?')[0]
    
    # Các pattern cho URL trang Facebook
    patterns = [
        r'facebook\.com/pages/[^/]+/(\d+)',    # facebook.com/pages/NAME/ID
        r'facebook\.com/([a-zA-Z0-9.]+)/?$',   # facebook.com/pagename
        r'fb\.com/([a-zA-Z0-9.]+)/?$'          # fb.com/pagename
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Nếu không tìm thấy qua regex, thử truy cập trang để lấy metadata
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm meta tag chứa ID trang
            meta_page_id = soup.find('meta', property='al:android:url')
            if meta_page_id and meta_page_id.get('content'):
                # Thường có dạng: fb://page/PAGE_ID
                fb_url_match = re.search(r'fb://page/(\d+)', meta_page_id['content'])
                if fb_url_match:
                    return fb_url_match.group(1)
            
            # Tìm kiếm trong HTML
            page_id_match = re.search(r'"pageID":"(\d+)"', response.text)
            if page_id_match:
                return page_id_match.group(1)
            
            # Lấy tên trang từ tiêu đề nếu không tìm thấy ID
            title = soup.find('title')
            if title:
                # Sử dụng đường dẫn làm ID
                path = url.rstrip('/').split('/')[-1]
                if path and not path.startswith('facebook.com'):
                    return path
    
    except Exception as e:
        logger.error(f"Lỗi khi truy cập URL Facebook: {str(e)}")
    
    # Nếu tất cả đều thất bại, sử dụng URL làm định danh
    path = url.rstrip('/').split('/')[-1]
    if path and not path.startswith('facebook.com'):
        return path
    
    return None

def get_youtube_channel_info(channel_id_or_url):
    """
    Lấy thông tin kênh YouTube (tên, URL)
    """
    channel_id = channel_id_or_url
    
    # Nếu là URL, trích xuất ID kênh
    if '/' in channel_id_or_url:
        channel_id = extract_youtube_channel_id(channel_id_or_url)
        if not channel_id:
            return None, None, None
    
    channel_url = f"https://www.youtube.com/channel/{channel_id}"
    
    try:
        response = requests.get(channel_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Tìm tên kênh
            title_tag = soup.find('title')
            channel_name = title_tag.text.split(' - YouTube')[0] if title_tag else None
            
            return channel_id, channel_name, channel_url
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin kênh YouTube: {e}")
    
    return channel_id, None, channel_url

def get_tiktok_channel_info(username_or_url):
    """
    Lấy thông tin kênh TikTok (tên, URL)
    """
    username = username_or_url
    
    # Nếu là URL, trích xuất username
    if '/' in username_or_url:
        username = extract_tiktok_username(username_or_url)
        if not username:
            return None, None, None
    
    channel_url = f"https://www.tiktok.com/@{username}"
    
    try:
        response = requests.get(channel_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Tìm tên kênh
            title_tag = soup.find('title')
            raw_title = title_tag.text if title_tag else None
            # Loại bỏ phần "(@username) TikTok"
            if raw_title:
                channel_name = re.sub(r'\(@[\w.]+\) TikTok.*', '', raw_title).strip()
            else:
                channel_name = username
            
            return username, channel_name, channel_url
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin kênh TikTok: {e}")
    
    return username, None, channel_url

def get_facebook_page_info(page_id_or_url):
    """
    Lấy thông tin trang Facebook (tên, URL)
    """
    page_id = page_id_or_url
    
    # Nếu là URL, trích xuất ID trang
    if '/' in page_id_or_url or ('facebook.com' in page_id_or_url or 'fb.com' in page_id_or_url):
        page_id = extract_facebook_page_id(page_id_or_url)
        if not page_id:
            return None, None, None
    
    # Nếu là số, thì là ID trang
    if page_id.isdigit():
        channel_url = f"https://www.facebook.com/{page_id}"
    else:
        # Nếu là tên trang
        channel_url = f"https://www.facebook.com/{page_id}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(channel_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Tìm tên trang
            title_tag = soup.find('title')
            if title_tag:
                # Loại bỏ phần " | Facebook" khỏi tiêu đề
                channel_name = re.sub(r' \| Facebook.*$', '', title_tag.text).strip()
            else:
                # Nếu không tìm thấy title, sử dụng ID làm tên
                channel_name = page_id
            
            return page_id, channel_name, channel_url
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin trang Facebook: {e}")
    
    return page_id, None, channel_url

def get_youtube_recent_videos(channel_id, max_results=5):
    """
    Lấy danh sách video mới nhất từ kênh YouTube
    
    Returns:
        list: Danh sách các video dưới dạng dict {video_id, title, url, published_at}
    """
    videos = []
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # Trích xuất thông tin video từ HTML
            video_id_matches = re.findall(r'"videoId":"([\w-]+)"', response.text)
            title_matches = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"}]},"thumbnail"', response.text)
            
            # Lấy các ID video duy nhất
            unique_video_ids = []
            for vid in video_id_matches:
                if vid not in unique_video_ids:
                    unique_video_ids.append(vid)
            
            # Tạo danh sách video
            for i, video_id in enumerate(unique_video_ids[:max_results]):
                title = title_matches[i] if i < len(title_matches) else None
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                videos.append({
                    'video_id': video_id,
                    'title': title,
                    'url': video_url,
                    'published_at': datetime.utcnow()  # Không có thông tin published_at chính xác
                })
    except Exception as e:
        logger.error(f"Lỗi khi lấy video YouTube gần đây: {e}")
    
    return videos

def get_tiktok_recent_videos(username, max_results=5):
    """
    Lấy danh sách video mới nhất từ kênh TikTok
    
    Returns:
        list: Danh sách các video dưới dạng dict {video_id, title, url, published_at}
    """
    videos = []
    
    try:
        # Sử dụng yt-dlp để lấy thông tin video
        from yt_dlp import YoutubeDL
        
        url = f"https://www.tiktok.com/@{username}"
        logger.info(f"Đang lấy video từ {url}")
        
        # Cấu hình yt-dlp
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': True,
            'no_warnings': True,
            'playlist_items': f'1-{max_results}'
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            try:
                # Lấy thông tin kênh và video
                info = ydl.extract_info(url, download=False)
                entries = info.get('entries', [])
                
                logger.info(f"Tìm thấy {len(entries)} video")
                
                for entry in entries:
                    try:
                        video_id = entry.get('id', '')
                        if not video_id:
                            video_id = entry.get('url', '').split('/')[-1]
                        
                        video_url = entry.get('url', f"https://www.tiktok.com/@{username}/video/{video_id}")
                        title = entry.get('title', '')
                        timestamp = entry.get('timestamp')
                        
                        if timestamp:
                            published_at = datetime.fromtimestamp(timestamp)
                        else:
                            published_at = datetime.utcnow()
                        
                        videos.append({
                            'video_id': video_id,
                            'title': title,
                            'url': video_url,
                            'published_at': published_at
                        })
                        logger.info(f"Đã thêm video {video_id}")
                        
                    except Exception as e:
                        logger.error(f"Lỗi khi xử lý video: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Lỗi khi lấy thông tin kênh: {str(e)}")
                
    except Exception as e:
        logger.error(f"Lỗi khi lấy video TikTok gần đây: {str(e)}")
    
    return videos

def get_facebook_recent_videos(page_id, max_results=5):
    """
    Lấy danh sách video mới nhất từ trang Facebook
    
    Returns:
        list: Danh sách các video dưới dạng dict {video_id, title, url, published_at}
    """
    videos = []
    if page_id.isdigit():
        url = f"https://www.facebook.com/{page_id}/videos"
    else:
        url = f"https://www.facebook.com/{page_id}/videos"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm tất cả các liên kết có thể chứa video
            video_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                # Tìm các liên kết có dạng facebook.com/username/videos/ID
                if '/videos/' in href and not href.endswith('/videos/'):
                    video_links.append(href)
            
            # Lọc các liên kết duy nhất
            unique_links = []
            for link in video_links:
                # Chỉ lấy URL đầy đủ
                if link.startswith('http') and link not in unique_links:
                    unique_links.append(link)
                # Nếu là đường dẫn tương đối, chuyển thành URL đầy đủ
                elif not link.startswith('http') and link not in unique_links:
                    full_link = f"https://www.facebook.com{link if link.startswith('/') else '/' + link}"
                    if full_link not in unique_links:
                        unique_links.append(full_link)
            
            # Tạo danh sách video
            for link in unique_links[:max_results]:
                # Trích xuất ID video từ URL
                video_id = get_facebook_video_id(link)
                
                # Nếu không tìm thấy ID, sử dụng URL làm ID
                if not video_id:
                    parts = link.split('/videos/')
                    if len(parts) > 1:
                        video_id = parts[1].split('/')[0].split('?')[0]
                    else:
                        # Gán một ID duy nhất dựa trên URL
                        video_id = link.split('/')[-1]
                
                # Tìm tiêu đề video (nếu có)
                title = None
                
                videos.append({
                    'video_id': video_id,
                    'title': title,
                    'url': link,
                    'published_at': datetime.utcnow()  # Không có thông tin published_at chính xác
                })
    except Exception as e:
        logger.error(f"Lỗi khi lấy video Facebook gần đây: {e}")
    
    return videos

def process_new_video(platform, video_info, language="vi"):
    """
    Trích xuất nội dung và tóm tắt video mới
    
    Args:
        platform (str): 'youtube', 'tiktok', hoặc 'facebook'
        video_info (dict): Thông tin video {video_id, title, url}
        language (str): Ngôn ngữ cho phụ đề
        
    Returns:
        str: Tóm tắt nội dung hoặc None nếu có lỗi
    """
    try:
        if platform == 'youtube':
            # Lấy phụ đề YouTube
            subtitles = get_youtube_transcript(video_info['video_id'], language)
            if "Không tìm thấy phụ đề" in subtitles:
                logger.warning(f"Không tìm thấy phụ đề cho video YouTube: {video_info['url']}")
                return None
            
            # Tóm tắt nội dung
            summary = summarize_transcript_with_g4f(subtitles, language)
            
        elif platform == 'tiktok':
            # Lấy caption TikTok
            content = analyze_tiktok_content(video_info['url'])
            if "Không thể" in content:
                logger.warning(f"Không thể trích xuất nội dung cho video TikTok: {video_info['url']}")
                return None
            
            # Tóm tắt nội dung
            summary = summarize_transcript_with_g4f(content, language)
            
        elif platform == 'facebook':
            # Lấy nội dung Facebook
            content = extract_facebook_content(video_info['url'])
            if "Không thể" in content:
                logger.warning(f"Không thể trích xuất nội dung cho video Facebook: {video_info['url']}")
                return None
            
            # Tóm tắt nội dung
            summary = summarize_transcript_with_g4f(content, language)
            
        else:
            logger.error(f"Nền tảng không được hỗ trợ: {platform}")
            return None
        
        if "Lỗi" in summary:
            logger.error(f"Lỗi khi tóm tắt nội dung: {summary}")
            return None
        
        return summary
    
    except Exception as e:
        logger.error(f"Lỗi khi xử lý video mới: {e}")
        return None