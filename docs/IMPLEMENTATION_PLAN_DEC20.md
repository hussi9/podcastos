# Implementation Plan - December 20, 2024

## Goal: Move from Demo to Production-Ready MVP

---

## Today's Schedule

### Session 1: Database & Auth (2-3 hours)
**Priority: CRITICAL**

#### 1.1 Supabase Setup (30 min)
```
[ ] Create Supabase project (if not exists)
[ ] Get connection credentials
[ ] Add to .env:
    - SUPABASE_URL
    - SUPABASE_ANON_KEY
    - SUPABASE_SERVICE_KEY
```

#### 1.2 Database Schema (30 min)
```sql
-- Users (handled by Supabase Auth)

-- Podcasts/Shows
CREATE TABLE shows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    name TEXT NOT NULL,
    description TEXT,
    voice_config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Episodes
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    show_id UUID REFERENCES shows(id),
    title TEXT NOT NULL,
    topic TEXT,
    audio_url TEXT,
    newsletter_url TEXT,
    duration_seconds INT,
    word_count INT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subscribers
CREATE TABLE subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    email TEXT NOT NULL,
    name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 1.3 Auth Integration (1-2 hours)
```
[ ] Install supabase-py
[ ] Create auth service (src/app/auth.py)
[ ] Add signup/login endpoints
[ ] Add auth middleware
[ ] Update UI with login/signup forms
[ ] Protect generation endpoints
```

---

### Session 2: User Content Input (1-2 hours)
**Priority: CRITICAL**

#### 2.1 URL Content Extractor (45 min)
```
[ ] Install trafilatura (pip install trafilatura)
[ ] Create content extractor service
[ ] Handle: Substack, Medium, WordPress, generic blogs
[ ] Extract: title, author, main content, publish date
```

#### 2.2 Update UI (45 min)
```
[ ] Add "Paste URL" input option
[ ] Add "Paste your content" textarea
[ ] Show extracted content preview
[ ] Connect to generation pipeline
```

---

### Session 3: Brand Voice (1-2 hours)
**Priority: HIGH**

#### 3.1 Voice Configuration Model (30 min)
```python
class BrandVoice:
    podcast_name: str
    host_name: str
    tone: str  # professional, casual, friendly
    custom_intro: Optional[str]
    custom_outro: Optional[str]
    tts_voice: str  # Kore, Aoede, Charon, etc.
```

#### 3.2 Voice Config UI (30 min)
```
[ ] Add voice configuration page
[ ] Voice preview/sample playback
[ ] Save to user profile
```

#### 3.3 Update Generation (30 min)
```
[ ] Inject brand voice into script prompts
[ ] Add intro/outro to audio
[ ] Test with different voices
```

---

### Session 4: Cloud Storage (1 hour)
**Priority: HIGH**

#### 4.1 S3/R2 Setup (30 min)
```
[ ] Create bucket (S3 or Cloudflare R2)
[ ] Get credentials
[ ] Add to .env:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - S3_BUCKET_NAME
    - S3_REGION
```

#### 4.2 Upload Service (30 min)
```
[ ] Create storage service (src/app/storage.py)
[ ] Upload audio files after generation
[ ] Upload newsletter HTML
[ ] Return public URLs
[ ] Update RSS feed with real URLs
```

---

### Session 5: Polish & Deploy (1-2 hours)
**Priority: HIGH**

#### 5.1 Error Handling (30 min)
```
[ ] Add try/catch to all endpoints
[ ] User-friendly error messages
[ ] Logging for debugging
```

#### 5.2 Environment Setup (30 min)
```
[ ] Create requirements.txt (production)
[ ] Create Procfile or railway.toml
[ ] Set up environment variables
```

#### 5.3 Deploy (30-60 min)
```
[ ] Push to GitHub
[ ] Connect to Railway/Vercel
[ ] Configure domain
[ ] Test production endpoints
```

---

## Files to Create/Modify

### New Files
```
src/app/auth.py          - Supabase authentication
src/app/database.py      - Database operations
src/app/storage.py       - S3/R2 file storage
src/app/content_input.py - URL/text content extraction
src/app/brand_voice.py   - Voice configuration
```

### Modified Files
```
src/app/main.py          - Add auth, new endpoints
src/app/rss_feed.py      - Use real URLs
requirements.txt         - Add new dependencies
.env.example             - Document all env vars
```

---

## API Endpoints to Add

### Auth
```
POST /api/auth/signup     - Create account
POST /api/auth/login      - Login
POST /api/auth/logout     - Logout
GET  /api/auth/me         - Current user
```

### Content Input
```
POST /api/content/from-url    - Extract from URL
POST /api/content/from-text   - Use pasted text
```

### Voice Config
```
GET  /api/voice/config        - Get user's voice config
POST /api/voice/config        - Save voice config
GET  /api/voice/preview/:id   - Preview voice sample
```

### Shows & Episodes
```
GET  /api/shows               - List user's shows
POST /api/shows               - Create show
GET  /api/shows/:id/episodes  - List episodes
```

---

## Dependencies to Add

```txt
# requirements.txt additions
supabase>=2.0.0
trafilatura>=1.6.0
boto3>=1.34.0           # For S3
python-jose>=3.3.0      # JWT handling
```

---

## Environment Variables Needed

```bash
# .env.example

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Storage (S3 or R2)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
S3_BUCKET_NAME=podcastos-files
S3_REGION=us-east-1
# Or for Cloudflare R2:
R2_ACCOUNT_ID=xxx
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx

# Email
SENDGRID_API_KEY=SG.xxx
FROM_EMAIL=hello@podcastos.com

# Stripe (later)
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# App
BASE_URL=https://podcastos.com
```

---

## Success Criteria for Today

### Must Complete
- [ ] Supabase auth working (signup/login)
- [ ] Database storing episodes
- [ ] URL content extraction working
- [ ] Basic brand voice config

### Nice to Have
- [ ] S3 storage working
- [ ] Deployed to staging
- [ ] Custom domain configured

### End of Day State
```
User can:
1. Sign up / Log in
2. Paste a URL or content
3. Configure basic voice settings
4. Generate newsletter + podcast
5. See their history
6. Download/distribute content
```

---

## Quick Start Commands

```bash
# Install new dependencies
pip install supabase trafilatura boto3

# Run locally
python run_app.py --port 8080 --reload

# Test endpoints
curl http://localhost:8080/api/health
curl http://localhost:8080/api/auth/me
```

---

## Notes

- Focus on getting auth + database FIRST (everything else depends on it)
- URL extraction is quick win for differentiation
- Voice config can be minimal initially (just name + voice selection)
- Storage can use local for now, upgrade to S3 later
- Don't get stuck on perfect - get it working first
