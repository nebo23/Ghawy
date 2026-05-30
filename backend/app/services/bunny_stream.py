import os
import requests
import logging

logger = logging.getLogger(__name__)

def get_video_duration_minutes(bunny_video_url: str) -> int:
    """
    Extract library_id and video_id from bunny_video_url and fetch duration from Bunny.net API.
    Returns duration in minutes. Defaults to 0 if API key is missing or request fails.
    """
    if not bunny_video_url:
        return 0

    api_key = os.environ.get("BUNNY_API_KEY")
    if not api_key:
        logger.warning("BUNNY_API_KEY not found in environment. Cannot fetch video duration automatically.")
        return 0

    # URL format: https://iframe.mediadelivery.net/embed/LIBRARY_ID/VIDEO_ID
    try:
        parts = bunny_video_url.split('/embed/')
        if len(parts) != 2:
            return 0
            
        lib_and_vid = parts[1].split('/')
        if len(lib_and_vid) < 2:
            return 0
            
        library_id = lib_and_vid[0]
        video_id = lib_and_vid[1].split('?')[0] # Remove any query params
        
        url = f"https://video.bunnycdn.com/library/{library_id}/videos/{video_id}"
        headers = {
            "AccessKey": api_key,
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # length is typically in seconds
            length_seconds = data.get('length', 0)
            return int(round(length_seconds / 60.0))
        else:
            logger.error(f"Failed to fetch Bunny video metadata. Status: {response.status_code}, Body: {response.text}")
            return 0
            
    except Exception as e:
        logger.error(f"Error fetching Bunny video duration: {e}")
        return 0
