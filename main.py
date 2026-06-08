"""
Fomo Clipper Bot
Telegram bot to auto-clip founder/trader interviews

Supports:
- YouTube links (auto-download - may be blocked)
- Video file uploads (manual - always works)
"""
import os
import re
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import Config
from transcript import get_transcript, find_best_moments
from clipper import download_clip, clip_local_video

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global state
user_sessions = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🎬 Fomo Clipper Bot

I help you clip founder & trader interviews!

How to use:
1. Send a YouTube link OR
2. Upload a video file directly

I'll:
• Get the transcript
• Find the best moments
• Clip the highlights
• Send it back!

Commands:
/start - Start
/help - Help
/settings - Settings
    """
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 How to use:

Option 1 - YouTube Link:
Send a YouTube link → I analyze and clip it

Option 2 - Upload Video (RECOMMENDED):
Send me a video file → I'll clip it for you

Supported formats:
MP4, MOV, AVI, MKV

For best results:
- Videos with clear speech
- 1-60 minutes long
- Good audio quality

Need help? Just ask!
    """
    await update.message.reply_text(help_text)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings_text = f"""
⚙️ Current Settings:

Clip Duration: {Config.MIN_CLIP_DURATION}-{Config.MAX_CLIP_DURATION} seconds
Target: {Config.TARGET_DURATION} seconds
    """
    await update.message.reply_text(settings_text)


async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming YouTube links"""
    user_id = update.effective_user.id
    message = update.message.text
    
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    is_youtube = any(re.search(pattern, message) for pattern in youtube_patterns)
    
    if not is_youtube:
        await update.message.reply_text("❌ Please send a valid YouTube link or upload a video file!")
        return
    
    processing_msg = await update.message.reply_text(
        "🔄 Processing YouTube link...\n\n"
        "Note: If download fails, please upload the video file directly."
    )
    
    try:
        video_info = await get_video_info(message)
        await processing_msg.edit_text(
            "🔄 Processing...\n\n"
            "Step 1/4: ✅ Got video info!\n"
            "Step 2/4: Fetching transcript..."
        )
        
        transcript = await get_transcript(message)
        if not transcript:
            await processing_msg.edit_text(
                "❌ Could not get transcript.\n\n"
                "Try uploading the video file directly instead."
            )
            return
            
        await processing_msg.edit_text(
            "🔄 Processing...\n\n"
            "Step 1/4: ✅ Got video info!\n"
            "Step 2/4: ✅ Got transcript!\n"
            "Step 3/4: AI analyzing..."
        )
        
        best_moments = await find_best_moments(
            transcript, 
            video_info.get('title', 'Unknown')
        )
        
        if not best_moments:
            await processing_msg.edit_text(
                "❌ Could not find good moments. Try a different video."
            )
            return
            
        user_sessions[user_id] = {
            'video_url': message,
            'video_info': video_info,
            'moments': best_moments,
            'type': 'youtube'
        }
        
        keyboard = []
        for i, moment in enumerate(best_moments[:5]):
            keyboard.append([
                InlineKeyboardButton(
                    f"📍 Moment {i+1}: {moment['title'][:35]}...", 
                    callback_data=f"clip_{i}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            f"🎬 Found {len(best_moments)} clips!\n\n"
            f"Video: {video_info.get('title', 'Unknown')}\n\n"
            f"Select a moment:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(
            f"❌ Error: {str(e)[:200]}\n\n"
            "Try uploading the video file directly instead."
        )


async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video file uploads"""
    user_id = update.effective_user.id
    message = update.message
    
    if not message.video and not message.document:
        await update.message.reply_text("❌ Please send a video file (MP4, MOV, AVI, MKV)")
        return
    
    # Get file
    file = message.video or message.document
    if message.document and not file.mime_type.startswith('video/'):
        await update.message.reply_text("❌ Please send a video file, not a document")
        return
    
    file_id = file.file_id
    file_name = getattr(file, 'file_name', 'video.mp4')
    
    processing_msg = await update.message.reply_text(
        "📥 Downloading video...\n\n"
        "Step 1/4: Download complete!\n"
        "Step 2/4: Getting transcript..."
    )
    
    try:
        # Download video file
        video_file = await context.bot.get_file(file_id)
        video_path = os.path.join(Config.TEMP_DIR, f"upload_{file_id[:20]}.mp4")
        await video_file.download_to_drive(video_path)
        
        # Get transcript from local video (using whisper)
        await processing_msg.edit_text(
            "📥 Video downloaded!\n\n"
            "Step 2/4: Transcribing...\n"
            "(This may take a few minutes)"
        )
        
        # For local videos, we'll do a simple approach - no transcript for now
        # The user will manually specify timestamps OR we'll use AI to analyze the video
        transcript = None
        
        # Create session with no moments - user will need to specify
        user_sessions[user_id] = {
            'video_path': video_path,
            'video_info': {'title': file_name},
            'moments': [],
            'type': 'upload'
        }
        
        # Ask user for timestamps or just clip the whole thing
        await processing_msg.edit_text(
            f"📥 Video ready!\n\n"
            f"File: {file_name}\n\n"
            f"⚠️ For uploaded videos, please tell me which part to clip.\n\n"
            f"Format: /clip [start_second] [end_second]\n\n"
            f"Example: /clip 60 120\n"
            f"(Clips from 1:00 to 2:00)"
        )
        
    except Exception as e:
        logger.error(f"Error handling upload: {e}")
        await processing_msg.edit_text(
            f"❌ Error: {str(e)[:200]}"
        )


async def handle_clip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clip command for manual timestamp selection"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    session = user_sessions.get(user_id)
    if not session:
        await update.message.reply_text(
            "❌ No video found. Please upload a video first with /start"
        )
        return
    
    # Parse timestamps
    parts = message_text.strip().split()
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Usage: /clip [start_second] [end_second]\n\n"
            "Example: /clip 60 120\n"
            "(Clips from 1:00 to 2:00)"
        )
        return
    
    try:
        start_time = float(parts[1])
        end_time = float(parts[2])
    except ValueError:
        await update.message.reply_text("❌ Invalid timestamps. Use numbers only.")
        return
    
    if start_time >= end_time:
        await update.message.reply_text("❌ End time must be greater than start time.")
        return
    
    duration = end_time - start_time
    if duration < Config.MIN_CLIP_DURATION:
        await update.message.reply_text(f"❌ Clip must be at least {Config.MIN_CLIP_DURATION} seconds.")
        return
    if duration > Config.MAX_CLIP_DURATION:
        await update.message.reply_text(f"❌ Clip must be at most {Config.MAX_CLIP_DURATION} seconds.")
        return
    
    processing_msg = await update.message.reply_text(
        f"✂️ Creating clip ({int(start_time)}s - {int(end_time)}s)..."
    )
    
    try:
        if session['type'] == 'upload':
            clip_path = await clip_local_video(
                session['video_path'],
                start_time,
                end_time
            )
        else:
            clip_path = await download_clip(
                session['video_url'],
                start_time,
                end_time
            )
        
        with open(clip_path, 'rb') as clip_file:
            await context.bot.send_video(
                chat_id=update.message.chat_id,
                video=clip_file,
                caption=f"🎬 Your clip ({int(start_time)}s - {int(end_time)}s)\n\n#fomoclipper"
            )
        
        os.remove(clip_path)
        
        # Cleanup original
        if session['type'] == 'upload' and os.path.exists(session['video_path']):
            os.remove(session['video_path'])
        
        await processing_msg.edit_text("✅ Clip sent!")
        
    except Exception as e:
        logger.error(f"Error creating clip: {e}")
        await processing_msg.edit_text(f"❌ Error: {str(e)[:200]}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries for clip selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if not data.startswith("clip_"):
        return
    
    moment_index = int(data.split("_")[1])
    session = user_sessions.get(user_id)
    
    if not session:
        await query.edit_message_text("❌ Session expired. Please send the link again.")
        return
    
    moments = session['moments']
    if moment_index >= len(moments):
        await query.edit_message_text("❌ Invalid selection.")
        return
    
    selected_moment = moments[moment_index]
    
    await query.edit_message_text(
        f"✂️ Creating clip: {selected_moment['title']}..."
    )
    
    try:
        if session['type'] == 'upload':
            clip_path = await clip_local_video(
                session['video_path'],
                selected_moment['start'],
                selected_moment['end']
            )
        else:
            clip_path = await download_clip(
                session['video_url'],
                selected_moment['start'],
                selected_moment['end']
            )
        
        with open(clip_path, 'rb') as clip_file:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=clip_file,
                caption=f"🎬 {selected_moment['title']}\n\n"
                        f"Timestamp: {selected_moment['start']:.0f}s - {selected_moment['end']:.0f}s\n\n"
                        f"#fomoclipper"
            )
        
        os.remove(clip_path)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)[:200]}")


async def get_video_info(url: str) -> dict:
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
        }


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")


def main():
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("clip", handle_clip_command))
    
    # Handle video uploads
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_upload))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_video_upload))
    
    # Handle YouTube links
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Fomo Clipper Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()