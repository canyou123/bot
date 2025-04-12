import re
from youtube_transcript_api import YouTubeTranscriptApi

def get_youtube_video_id(url):
    regex = r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:[^/]+/.*|(?:v|e(?:mbed)?|watch|results\?search_query)=)|youtu\.be/|youtube\.com/(?:v|embed|watch\?v=|.+/))([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_youtube_channel_id(url):
    """
    Extract YouTube channel ID from a channel URL.
    Supports formats:
    - youtube.com/channel/UC...
    - youtube.com/c/ChannelName
    - youtube.com/user/Username
    - youtube.com/@username
    """
    # Direct channel ID format
    channel_pattern = r"youtube\.com/channel/(UC[\w-]+)"
    match = re.search(channel_pattern, url)
    if match:
        return match.group(1)

    # Custom URL or username format
    try:
        if "youtube.com/c/" in url or "youtube.com/user/" in url or "youtube.com/@" in url:
            return url.split("/")[-1]
    except Exception:
        return None

    return None

def get_youtube_transcript(video_id, language="vi"):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
        return " ".join([line["text"] for line in transcript])
    except Exception as e:
        return f"Không tìm thấy phụ đề hoặc có lỗi xảy ra"