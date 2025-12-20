# 🎙️ Desi Podcast Engine

**AI-powered daily podcast generator for the South Asian diaspora in the USA**

An automated system that creates engaging, conversational podcast episodes by:
1. Aggregating trending topics from Reddit, news, and immigration sources
2. Generating natural two-host dialogue using Google Gemini AI
3. Converting scripts to audio using ElevenLabs Text-to-Speech
4. Publishing via RSS feed for podcast platforms

## 🌟 Features

- **Multi-source Content Aggregation**
  - Reddit communities (ABCDesis, H1B, immigration, etc.)
  - News feeds (Times of India, Hindustan Times NRI sections)
  - USCIS official updates and Visa Bulletin tracking

- **AI-Powered Script Generation**
  - Natural conversational dialogue between two hosts
  - Culturally relevant content and perspectives
  - Practical advice and community insights

- **Professional Audio Generation**
  - High-quality ElevenLabs voices
  - Automatic audio stitching
  - MP3 output ready for distribution

- **Distribution Ready**
  - RSS feed generation
  - Compatible with Apple Podcasts, Spotify, Google Podcasts

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Google Gemini API key
- ElevenLabs API key
- (Optional) Reddit API credentials
- (Optional) Supabase for news integration

### Installation

```bash
# Clone the repository
cd /Users/airbook/devpro/desi-podcast-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` with your credentials:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# Optional (enhances content)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_key
```

### Run

```bash
# Start the API server
python main.py

# Or generate a single episode
python scheduler.py --once

# Preview today's content without generating
python scheduler.py --preview

# Generate script only (no audio, faster)
python scheduler.py --once --script-only
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/preview` | GET | Preview today's content |
| `/generate` | POST | Start episode generation |
| `/status/{id}` | GET | Check generation status |
| `/episodes` | GET | List all episodes |
| `/episodes/{id}` | GET | Get episode details |
| `/episodes/{id}/audio` | GET | Download episode audio |
| `/episodes/{id}/script` | GET | Get episode script |
| `/feed.xml` | GET | RSS podcast feed |

### Generate an Episode

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic_count": 5,
    "target_duration_minutes": 12,
    "generate_audio": true
  }'
```

## 🐳 Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f podcast-engine
```

## 📁 Project Structure

```
desi-podcast-engine/
├── main.py                 # FastAPI service
├── scheduler.py            # Scheduled generation
├── src/
│   ├── aggregators/        # Content sources
│   │   ├── reddit_aggregator.py
│   │   ├── news_aggregator.py
│   │   ├── uscis_aggregator.py
│   │   └── content_ranker.py
│   ├── generators/
│   │   └── script_generator.py  # Gemini AI scripts
│   ├── tts/
│   │   └── elevenlabs_tts.py    # Audio generation
│   ├── podcast_engine.py   # Main orchestrator
│   └── rss_generator.py    # RSS feed
├── config/
│   └── settings.py
├── output/
│   ├── episodes/           # Episode metadata
│   ├── scripts/            # Generated scripts
│   └── audio/              # Audio files
└── tests/
```

## 🎭 The Hosts

**Raj** - A pragmatic tech professional who immigrated 10 years ago. Focuses on practical advice, visa processes, and career growth. Warm but direct.

**Priya** - A second-generation Indian-American community organizer. Brings cultural context, emotional intelligence, and community perspectives.

## 💰 Cost Estimates

### With Google Cloud TTS (Recommended)
| Service | Tier | Monthly Cost |
|---------|------|--------------|
| Google Gemini | Pay-as-you-go | ~$10-20 |
| Google Cloud TTS | Free tier | **FREE** |
| Hosting (optional) | Basic VPS | ~$5-10 |
| **Total** | | **~$10-25/month** 🎉 |

### With ElevenLabs (Premium Quality)
| Service | Tier | Monthly Cost |
|---------|------|--------------|
| Google Gemini | Pay-as-you-go | ~$10-20 |
| ElevenLabs | Creator | $22 |
| Hosting (optional) | Basic VPS | ~$5-10 |
| **Total** | | **~$40-50/month** |

## 🔊 Setting Up Google Cloud TTS

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the **Cloud Text-to-Speech API**:
   - Go to **APIs & Services** → **Library**
   - Search "Cloud Text-to-Speech API"
   - Click **Enable**
4. Create an API key:
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **API Key**
5. Add to your `.env`:
   ```
   GOOGLE_TTS_API_KEY=your_api_key_here
   TTS_PROVIDER=google
   ```

### Free Tier Limits
- **Standard voices**: 4M characters/month FREE
- **Neural2 voices**: 1M characters/month FREE
- **Journey voices**: Pay per use (~$30/1M chars)
- A 12-min episode ≈ 15,000 characters
- **~65 FREE episodes/month!**

## 🔧 Customization

### Change Voices

Update the voice IDs in `.env`:
```env
ELEVENLABS_VOICE_1=voice_id_for_raj
ELEVENLABS_VOICE_2=voice_id_for_priya
```

### Add Content Sources

Edit `src/aggregators/reddit_aggregator.py` to add subreddits:
```python
DEFAULT_SUBREDDITS = [
    "ABCDesis",
    "YourNewSubreddit",
    ...
]
```

### Modify Episode Length

```env
EPISODE_LENGTH_MINUTES=15
```

## 📅 Scheduling

The scheduler runs daily at the configured hour (default 6 AM ET):

```bash
# Run scheduler service
python scheduler.py

# Or use cron
0 6 * * * cd /path/to/desi-podcast-engine && python scheduler.py --once
```

## 🤝 Integration with DesiVibe

This engine integrates with DesiVibe's news pipeline:
- Fetches articles from the `nw_articles` table
- Can be embedded as a player in the DesiVibe app
- RSS feed can be linked from the app

## 📝 License

MIT License - Feel free to use and modify!

## 🙏 Credits

Built for the South Asian community in America 🇮🇳🇺🇸

---

**Questions?** Open an issue or reach out at podcast@desivibe.com
