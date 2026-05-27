"""
Clipper module - Download and clip videos using yt-dlp and FFmpeg
"""
import os
import re
import logging
import tempfile
from pathlib import Path

import yt_dlp
import ffmpeg

from config import Config

logger = logging.getLogger(__name__)


async def download_clip(video_url: str, start_time: float, end_time: float, output_path: str = None) -> str:
    """
    Download a clip from a YouTube video
    
    Args:
        video_url: YouTube video URL
        start_time: Start time in seconds
        end_time: End time in seconds
        output_path: Optional custom output path
    
    Returns:
        Path to the downloaded clip
    """
    # Create temp directory if it doesn't exist
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    
    # Generate output filename
    if output_path is None:
        output_path = os.path.join(
            Config.TEMP_DIR, 
            f"clip_{int(start_time)}_{int(end_time)}.mp4"
        )
    
    # Ensure we don't overwrite existing files
    if os.path.exists(output_path):
        base_path = output_path.replace('.mp4', '')
        counter = 1
        while os.path.exists(f"{base_path}_{counter}.mp4"):
            counter += 1
        output_path = f"{base_path}_{counter}.mp4"
    
    # Calculate duration
    duration = end_time - start_time
    
    # yt-dlp options for clipping
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path.replace('.mp4', '.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'http_chunk_size': 10485760,  # 10MB chunks
        'retries': 3,
        'fragment_retries': 3,
    }
    
    logger.info(f"Downloading clip: {video_url} [{start_time:.0f}s - {end_time:.0f}s]")
    
    # Download the video (full video, we'll clip with ffmpeg)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract info first to get the actual filename
        info = ydl.extract_info(video_url, download=True)
        downloaded_path = ydl.prepare_filename(info)
    
    # Check if file exists
    if not os.path.exists(downloaded_path):
        raise FileNotFoundError(f"Downloaded file not found: {downloaded_path}")
    
    # Now clip using ffmpeg
    clipped_path = output_path
    
    try:
        # Use ffmpeg to clip the video
        (
            ffmpeg
            .input(downloaded_path, ss=start_time, t=duration)
            .output(
                clipped_path,
                vcodec='libx264',
                acodec='aac',
                audio_codec='aac',
                **{'b:a': '128k'},
                **{'b:v': '2000k'},
                preset='fast',
                movflags='+faststart'
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Clean up original download
        if os.path.exists(downloaded_path):
            os.remove(downloaded_path)
        
        logger.info(f"Clip saved to: {clipped_path}")
        return clipped_path
        
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        # If ffmpeg fails, try to return the original as fallback
        if os.path.exists(downloaded_path):
            return downloaded_path
        raise


async def get_video_thumbnail(url: str) -> str:
    """Get video thumbnail URL"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('thumbnail', '')


async def get_video_duration(url: str) -> float:
    """Get video duration in seconds"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('duration', 0)


def format_duration(seconds: float) -> str:
    """Format seconds to MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"