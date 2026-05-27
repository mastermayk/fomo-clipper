# 🎬 Fomo Clipper Bot

Telegram bot that automatically clips founder & trader interview highlights using AI.

## Features

- **AI-Powered Analysis** - Analyzes transcripts to find the best moments
- **Auto-Clipping** - Creates 20-60 second clips automatically  
- **Cloud Processing** - No local downloads needed
- **Telegram Interface** - Easy to use bot commands

## Quick Setup

### 1. Create Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the **Bot Token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Get OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com)
2. Create an account or sign in
3. Go to API Keys section
4. Create a new secret key
5. Copy the key

### 3. Configure Bot

```bash
# Clone the repo
git clone <this-repo>
cd fomo-clipper

# Copy example config
cp .env.example .env

# Edit .env file with your tokens
```

Your `.env` should have:
```
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
ADMIN_USER_ID=your_telegram_user_id
```

### 4. Deploy to Cloud

#### Option A: Render (Free)

1. Connect your GitHub repo to Render
2. Create a new "Web Service"
3. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
4. Add Environment Variables in Render dashboard

#### Option B: Railway

1. Install Railway CLI
2. Run `railway init`
3. Add environment variables
4. Deploy with `railway up`

#### Option C: VPS/Server

```bash
# Install dependencies
pip install -r requirements.txt

# Install FFmpeg
# Ubuntu: sudo apt install ffmpeg
# Mac: brew install ffmpeg
# Windows: Download from ffmpeg.org

# Run the bot
python main.py
```

## Usage

1. Start the bot: `/start`
2. Send a YouTube link
3. Bot analyzes the video and finds best moments
4. Select which moment to clip
5. Bot sends back the clipped video!

## Project Structure

```
fomo-clipper/
├── main.py           # Bot entry point
├── config.py        # Configuration
├── transcript.py    # YouTube transcript + AI analysis
├── clipper.py       # Video downloading & clipping
├── requirements.txt # Python dependencies
├── .env.example     # Environment template
└── README.md       # This file
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| BOT_TOKEN | Yes | Telegram bot token |
| OPENAI_API_KEY | Yes | OpenAI API key |
| ADMIN_USER_ID | No | Your Telegram user ID |
| MIN_CLIP_DURATION | No | Minimum clip length (default: 20) |
| MAX_CLIP_DURATION | No | Maximum clip length (default: 60) |
| TARGET_DURATION | No | Target clip length (default: 45) |

## Requirements

- Python 3.9+
- FFmpeg (for video clipping)
- Telegram Bot API
- OpenAI API (for AI analysis)

## License

MIT