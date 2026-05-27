"""
Configuration for Fomo Clipper Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0')) if os.getenv('ADMIN_USER_ID', '0').isdigit() else 0
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    
    # Clip settings
    MIN_CLIP_DURATION = int(os.getenv('MIN_CLIP_DURATION', '20'))
    MAX_CLIP_DURATION = int(os.getenv('MAX_CLIP_DURATION', '60'))
    TARGET_DURATION = int(os.getenv('TARGET_DURATION', '45'))
    
    # Temp directory
    TEMP_DIR = os.getenv('TEMP_DIR', 'C:\\Temp\\fomo-clips')
    
    # FFmpeg path (Windows)
    FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')
    
    @classmethod
    def validate(cls):
        """Validate required config"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required!")
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required!")
        if not cls.ADMIN_USER_ID:
            print("⚠️ ADMIN_USER_ID not set - admin features disabled")