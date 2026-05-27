#!/bin/bash
# Deploy script for Fomo Clipper Bot

echo "🎬 Fomo Clipper - Deploy Script"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️ FFmpeg not found!"
    echo "Please install FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  Mac: brew install ffmpeg"
    echo "  Windows: Download from https://ffmpeg.org"
fi

# Run the bot
echo "🤖 Starting Fomo Clipper Bot..."
python main.py