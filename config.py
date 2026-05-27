"""
Clipper module - Download and clip videos using yt-dlp and FFmpeg
"""
import os
import logging
import yt_dlp
import ffmpeg

from config import Config

logger = logging.getLogger(__name__)


async def download_clip(video_url: str, start_time: float, end_time: float, output_path: str = None) -> str:
    """Download and clip a YouTube video"""
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    
    if output_path is None:
        output_path = os.path.join(Config.TEMP_DIR, f"clip_{int(start_time)}_{int(end_time)}.mp4")
    
    duration = end_time - start_time
    
    # Multiple download approaches to bypass blocks
    download_methods = [
        # Method 1: Standard
        {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path.replace('.mp4', '.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractor_retries': 3,
            'skip_download': False,
        },
        # Method 2: Alternative format
        {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_path.replace('.mp4', '.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractor_retries': 5,
            'skip_download': False,
        },
    ]
    
    downloaded_path = None
    last_error = None
    
    for method_opts in download_methods:
        try:
            logger.info(f"Downloading: {video_url}")
            with yt_dlp.YoutubeDL(method_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                downloaded_path = ydl.prepare_filename(info)
            if downloaded_path and os.path.exists(downloaded_path):
                break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Download failed: {e}")
            continue
    
    if not downloaded_path or not os.path.exists(downloaded_path):
        raise Exception(f"YouTube blocked download. Try a public video or download manually.\n\nError: {last_error}")
    
    # Clip with ffmpeg
    clipped_path = output_path
    try:
        (
            ffmpeg
            .input(downloaded_path, ss=start_time, t=duration)
            .output(clipped_path, vcodec='libx264', acodec='aac', **{'b:a': '128k'}, **{'b:v': '2000k'}, preset='fast')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        if os.path.exists(downloaded_path):
            os.remove(downloaded_path)
        return clipped_path
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e}")
        if os.path.exists(downloaded_path):
            return downloaded_path
        raise


async def get_video_thumbnail(url: str) -> str:
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('thumbnail', '')


async def get_video_duration(url: str) -> float:
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('duration', 0)
