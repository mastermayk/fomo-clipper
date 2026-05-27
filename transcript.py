"""
Transcript module - Get YouTube transcripts and find best moments using AI
"""
import re
import logging
from typing import List, Dict, Optional

from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=Config.OPENAI_API_KEY)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def get_transcript(url: str) -> Optional[List[Dict]]:
    """Get transcript from YouTube video"""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            logger.error(f"Could not extract video ID from {url}")
            return None
        
        # Try to get transcript
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to get English transcript first
        try:
            transcript = transcript_list.find_transcript(['en'])
            transcript_data = transcript.fetch()
            return transcript_data
        except:
            pass
        
        # Try to get any available transcript
        try:
            transcript = transcript_list.find_generated_transcript(['en', 'en-US'])
            transcript_data = transcript.fetch()
            return transcript_data
        except:
            pass
        
        # Try to get transcript in any language
        try:
            transcript = transcript_list.find_transcript(
                list(transcript_list._transcripts.keys())
            )
            transcript_data = transcript.fetch()
            return transcript_data
        except Exception as e:
            logger.error(f"Error getting transcript: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting transcript: {e}")
        return None


def format_transcript_for_ai(transcript: List[Dict], max_chars: int = 15000) -> str:
    """Format transcript for AI analysis"""
    formatted = []
    current_time = 0
    
    for entry in transcript:
        start = entry['start']
        text = entry['text']
        
        # Convert to readable timestamp
        minutes = int(start // 60)
        seconds = int(start % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"
        
        formatted.append(f"{timestamp} {text}")
        
        # Check if we need to truncate
        if len('\n'.join(formatted)) > max_chars:
            break
    
    return '\n'.join(formatted)


async def find_best_moments(transcript: List[Dict], video_title: str, num_moments: int = 5) -> List[Dict]:
    """Use AI to find the best moments to clip based on the brief criteria"""
    
    # Format transcript
    transcript_text = format_transcript_for_ai(transcript)
    
    # Brief criteria from the user
    brief_criteria = """
Focus on moments where the speaker has:
- Strong takes on markets (BTC, macro, trends)
- Unique insights or "alpha"
- Clear explanations of complex ideas
- Contrarian opinions
- Lessons from experience (wins, losses, mistakes)
- Actionable advice

Avoid:
- Slow conversations with no clear takeaway
- Generic opinions like "markets are uncertain"
- Overly technical segments without clear explanation
- Long-winded answers without a punchline or insight

Clip structure should be:
- Hook → strong statement or claim
- Context → who is speaking / why it matters
- Insight → the actual value
- Clean ending → stop when the point lands

Good hooks:
- "Most traders misunderstand this…"
- "The biggest mistake I see right now is…"
- "Here's what people are missing about this market…"
"""
    
    # Create prompt for GPT
    prompt = f"""You are an expert content clipper for a crypto/finance content channel. 

Video Title: {video_title}

{brief_criteria}

IMPORTANT CLIPPING GUIDELINES:
- Target clip duration: {Config.TARGET_DURATION} seconds (min: {Config.MIN_CLIP_DURATION}, max: {Config.MAX_CLIP_DURATION})
- Start clips with the strongest line possible (the hook)
- Each clip should be able to stand alone without too much context
- Clips should teach something or provide clear insight

Below is the transcript of the video. Analyze it and identify the {num_moments} BEST moments to clip.

Transcript:
{transcript_text}

Respond with ONLY a JSON array of {num_moments} moments in this exact format:
[
  {{"start": seconds, "end": seconds, "title": "Brief description of the clip", "reason": "Why this is a good clip"}}
]

Ensure:
- start and end are in seconds
- Each clip is between {Config.MIN_CLIP_DURATION} and {Config.MAX_CLIP_DURATION} seconds
- The start time captures the hook/strongest line
- End time captures a clean ending point
- Titles are concise (max 60 characters)
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert content clipper. Analyze transcripts and find the best moments to clip. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        # Parse the response
        content = response.choices[0].message.content
        
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_content = content[json_start:json_end]
                moments = eval(json_content)
            else:
                moments = eval(content)
            
            # Validate and clean up moments
            valid_moments = []
            for m in moments:
                start = float(m.get('start', 0))
                end = float(m.get('end', start + Config.TARGET_DURATION))
                title = str(m.get('title', 'Untitled'))[:60]
                reason = str(m.get('reason', ''))
                
                # Ensure duration is within limits
                duration = end - start
                if duration < Config.MIN_CLIP_DURATION:
                    end = start + Config.MIN_CLIP_DURATION
                elif duration > Config.MAX_CLIP_DURATION:
                    end = start + Config.MAX_CLIP_DURATION
                
                valid_moments.append({
                    'start': start,
                    'end': end,
                    'title': title,
                    'reason': reason
                })
            
            return valid_moments
            
        except Exception as e:
            logger.error(f"Error parsing moments JSON: {e}")
            logger.error(f"Response content: {content}")
            return []
            
    except Exception as e:
        logger.error(f"Error finding best moments: {e}")
        return []