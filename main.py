"""
Fomo Clipper Bot
Telegram bot to auto-clip founder/trader interviews
"""

import os
import re
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import Config
from transcript import get_transcript, find_best_moments
from clipper import download_clip

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global state
user_sessions = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = """
🎬 Fomo Clipper Bot

I help you clip founder & trader interviews automatically!

Send me a YouTube link and I'll:
1. Get the video transcript
2. Find the best moments (based on your brief)
3. Clip the highlights
4. Send it back to you

Commands:
/start - Start the bot
/help - Get help
/settings - Configure clip preferences

Just send me a YouTube link to get started!
    """
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📖 How to use Fomo Clipper:

1. Send a YouTube link
2. Wait for AI to analyze
3. Review suggested clips
4. Get your clipped video!

🎯 Best for:
- Founder interviews
- Trader insights
- Market analysis
- Alpha calls

Supported platforms:
- YouTube (primary)
- More coming soon!

Need help? Just ask!
    """
    await update.message.reply_text(help_text)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command"""
    settings_text = """
⚙️ Current Settings:

Clip Duration: 20-60 seconds
Target Duration: 45 seconds
Min Duration: 20 seconds
Max Duration: 60 seconds

To change settings, contact the admin.
    """
    await update.message.reply_text(settings_text)


async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming YouTube links"""
    user_id = update.effective_user.id
    message = update.message.text
    
    # Check if it's a valid YouTube link
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    is_youtube = any(re.search(pattern, message) for pattern in youtube_patterns)
    
    if not is_youtube:
        await update.message.reply_text("❌ Please send a valid YouTube link!")
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "🔄 Processing your link...\n\n"
        "Step 1/4: Getting video info..."
    )
    
    try:
        # Get video info
        video_info = await get_video_info(message)
        await processing_msg.edit_text(
            "🔄 Processing your link...\n\n"
            "Step 1/4: ✅ Got video info!\n"
            "Step 2/4: Fetching transcript..."
        )
        
        # Get transcript
        transcript = await get_transcript(message)
        if not transcript:
            await processing_msg.edit_text(
                "❌ Could not get transcript for this video.\n\n"
                "The video might not have captions available."
            )
            return
            
        await processing_msg.edit_text(
            "🔄 Processing your link...\n\n"
            "Step 1/4: ✅ Got video info!\n"
            "Step 2/4: ✅ Got transcript!\n"
            "Step 3/4: AI analyzing best moments..."
        )
        
        # Find best moments using AI
        best_moments = await find_best_moments(
            transcript, 
            video_info.get('title', 'Unknown')
        )
        
        if not best_moments:
            await processing_msg.edit_text(
                "❌ Could not find good moments to clip.\n\n"
                "The video might not have enough valuable content."
            )
            return
            
        await processing_msg.edit_text(
            "🔄 Processing your link...\n\n"
            "Step 1/4: ✅ Got video info!\n"
            "Step 2/4: ✅ Got transcript!\n"
            "Step 3/4: ✅ AI found best moments!\n"
            "Step 4/4: Creating clips..."
        )
        
        # Store session data
        user_sessions[user_id] = {
            'video_url': message,
            'video_info': video_info,
            'moments': best_moments
        }
        
        # Show user the moments found
        keyboard = []
        for i, moment in enumerate(best_moments[:5]):
            keyboard.append([
                InlineKeyboardButton(
                    f"📍 Moment {i+1}: {moment['title'][:40]}...", 
                    callback_data=f"clip_{i}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            f"🎬 Found {len(best_moments)} potential clips!\n\n"
            f"Video: {video_info.get('title', 'Unknown')}\n\n"
            f"Select a moment to clip:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error processing link: {e}")
        await processing_msg.edit_text(
            f"❌ Error: {str(e)}\n\n"
            "Please try again or send a different link."
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries for clip selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if not data.startswith("clip_"):
        return
    
    moment_index = int(data.split("_")[1])
    
    # Get session data
    session = user_sessions.get(user_id)
    if not session:
        await query.edit_message_text("❌ Session expired. Please send the link again.")
        return
    
    # Get the selected moment
    moments = session['moments']
    if moment_index >= len(moments):
        await query.edit_message_text("❌ Invalid selection.")
        return
    
    selected_moment = moments[moment_index]
    video_url = session['video_url']
    
    # Show downloading message
    await query.edit_message_text(
        "✂️ Creating your clip...\n\n"
        "This may take a minute..."
    )
    
    try:
        # Download and clip the video
        clip_path = await download_clip(
            video_url,
            selected_moment['start'],
            selected_moment['end']
        )
        
        # Send the clip
        with open(clip_path, 'rb') as clip_file:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=clip_file,
                caption=f"🎬 {selected_moment['title']}\n\n"
                        f"Timestamp: {selected_moment['start']:.0f}s - {selected_moment['end']:.0f}s\n\n"
                        f"#fomoclipper"
            )
        
        # Clean up
        os.remove(clip_path)
        
    except Exception as e:
        logger.error(f"Error creating clip: {e}")
        await query.edit_message_text(
            f"❌ Error creating clip: {str(e)}\n\n"
            "Please try again."
        )


async def get_video_info(url: str) -> dict:
    """Get video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'uploader': info.get('uploader', 'Unknown'),
            'description': info.get('description', '')[:500]
        }


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Main function to run the bot"""
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("🤖 Fomo Clipper Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()