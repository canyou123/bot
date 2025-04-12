import re
import requests
import yt_dlp
from bs4 import BeautifulSoup

def get_tiktok_video_id(url):
    """
    Extract the TikTok video ID from a TikTok URL
    
    Args:
        url (str): The TikTok video URL
        
    Returns:
        str: The video ID if found, None otherwise
    """
    patterns = [
        r'tiktok\.com/@[\w\.]+/video/(\d+)',
        r'vm\.tiktok\.com/(\w+)',
        r'vt\.tiktok\.com/(\w+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
                try:
                    response = requests.head(url, allow_redirects=True)
                    final_url = response.url
                    match = re.search(r'tiktok\.com/@[\w\.]+/video/(\d+)', final_url)
                    if match:
                        return match.group(1)
                except Exception:
                    return None
            else:
                return match.group(1)
    
    return None

def download_tiktok_video(url, output_path):
    """
    Download TikTok video using yt-dlp
    
    Args:
        url (str): TikTok video URL
        output_path (str): Path to save the video
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception:
        return False

def extract_tiktok_hashtags(url):
    """
    Extract hashtags from TikTok video description
    
    Args:
        url (str): TikTok video URL
        
    Returns:
        list: List of hashtags found in the video description
    """
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all hashtags in the video description
        hashtags = []
        description = soup.find('meta', {'property': 'og:description'})
        if description:
            desc_text = description.get('content', '')
            hashtags = re.findall(r'#\w+', desc_text)
        
        return hashtags
    except Exception:
        return []

def analyze_tiktok_content(url):
    """
    Analyze TikTok video content and extract hashtags
    
    Args:
        url (str): TikTok video URL
        
    Returns:
        dict: Dictionary containing video information and hashtags
    """
    video_id = get_tiktok_video_id(url)
    if not video_id:
        return {"error": "Không thể xác định ID video TikTok"}
    
    hashtags = extract_tiktok_hashtags(url)
    
    return {
        "video_id": video_id,
        "hashtags": hashtags
    }