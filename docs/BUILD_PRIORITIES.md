# Build Priorities: What's Missing for Product-Market Fit

## Current State vs Customer Need

| You Built | Customer Needs | Gap |
|-----------|----------------|-----|
| Scrapes HN, Reddit, News | Input THEIR content (newsletter, blog) | **Critical** |
| Generic voice | Custom brand voice + persona | **High** |
| Manual export (WAV) | Auto-publish to Spotify/Apple | **Critical** |
| No onboarding | 3-minute setup wizard | **High** |
| No analytics | Listen counts, engagement | **Medium** |
| CLI-based | Beautiful web dashboard | **High** |

---

## Priority 1: Content Input (CRITICAL)

**Current:** You aggregate from public sources
**Need:** Accept customer's own content

### Build This:
```python
# New input sources to support
class ContentInput:
    # 1. URL/RSS - Convert their blog/newsletter
    async def from_url(self, url: str) -> Content

    # 2. Text paste - Direct content input
    async def from_text(self, text: str, title: str) -> Content

    # 3. Document upload - PDF, DOCX
    async def from_document(self, file: UploadFile) -> Content

    # 4. Newsletter integration - Substack, Beehiiv webhooks
    async def from_webhook(self, payload: dict) -> Content
```

### User Flow:
```
1. User pastes their newsletter URL
2. We extract the content
3. We ADD research/context from our sources
4. We generate script in their voice
5. Output: Their content + our enhancement
```

---

## Priority 2: Brand Voice (HIGH)

**Current:** Generic podcast voice
**Need:** Sounds like THEIR brand

### Build This:
```python
class BrandVoice(BaseModel):
    # Identity
    podcast_name: str
    tagline: str
    host_name: str  # "I'm Sarah, and this is..."

    # Personality
    tone: str  # professional, casual, witty, serious
    speaking_style: str  # "explains complex topics simply"
    catchphrases: list[str]  # "Let's dive in", "Here's the thing"

    # Bookends
    custom_intro: Optional[str]  # "Hey, it's Sarah with The Daily Brew..."
    custom_outro: Optional[str]  # "Thanks for listening..."

    # Voice
    tts_voice: str  # Kore, Aoede, etc.
    speaking_rate: float  # 0.9 - 1.2
```

### Prompt Engineering:
```python
BRANDED_SEGMENT_PROMPT = """You are {host_name}, host of {podcast_name}.

Your personality: {speaking_style}
Your tone: {tone}
Your catchphrases: {catchphrases}

Write this segment as if YOU are speaking to YOUR audience.
Sound like a real person, not a generic AI host.

Topic: {topic}
Key points from their content: {content_summary}
Additional research: {research}

Remember: This is THEIR content, enhanced with context. Stay true to their voice.
"""
```

---

## Priority 3: Distribution (CRITICAL)

**Current:** Manual WAV export
**Need:** One-click publish everywhere

### Build This:
```python
class DistributionManager:
    # Platform connections
    async def connect_spotify(self, oauth_token: str)
    async def connect_apple(self, credentials: dict)
    async def connect_youtube(self, oauth_token: str)

    # Publishing
    async def publish_episode(
        self,
        episode: AudioEpisode,
        platforms: list[str],  # ["spotify", "apple", "youtube"]
        schedule_time: Optional[datetime] = None,
    ) -> PublishResult

    # RSS Feed (for platforms that need it)
    def generate_rss_feed(self, podcast: Podcast) -> str
```

### Integration Options:
1. **Spotify for Podcasters API** - Direct upload
2. **Apple Podcasts Connect** - Via RSS or API
3. **Podcast Hosting** - Partner with Transistor, Buzzsprout, Anchor
4. **Self-hosted RSS** - Generate feed they can submit

---

## Priority 4: Onboarding Wizard (HIGH)

**Current:** CLI commands
**Need:** 3-minute web setup

### Build This:
```
Step 1: "What's your podcast about?"
        [Newsletter name] covering [topic]

Step 2: "Where's your content?"
        ○ Connect Substack
        ○ Connect RSS feed
        ○ I'll paste content manually

Step 3: "How should it sound?"
        [Play voice samples]
        Select: Kore / Aoede / Charon

Step 4: "Generate your first episode"
        [Processing... 2 minutes]

Step 5: "Your podcast is ready!"
        [Play preview]
        [Publish] [Edit] [Download]
```

---

## Priority 5: Billing & Auth (REQUIRED)

**Current:** None
**Need:** User accounts + Stripe

### Build This:
```python
# Auth (use Supabase)
- Email/password signup
- OAuth (Google, Twitter)
- User profiles with podcast settings

# Billing (use Stripe)
- Subscription tiers: $49, $99, $249, $499
- Usage tracking: episodes/month
- Upgrade prompts when limit hit

# Limits by tier
TIER_LIMITS = {
    "starter": {"episodes_per_month": 4, "podcasts": 1},
    "creator": {"episodes_per_month": 12, "podcasts": 1},
    "pro": {"episodes_per_month": 30, "podcasts": 3},
    "business": {"episodes_per_month": -1, "podcasts": 10},  # -1 = unlimited
}
```

---

## Immediate Action Plan

### Week 1: Content Input
- [ ] Build URL-to-content extractor (use trafilatura or newspaper3k)
- [ ] Build text paste input
- [ ] Modify pipeline to accept external content
- [ ] Test: Paste newsletter URL → Get podcast

### Week 2: Brand Voice
- [ ] Build brand voice configuration UI
- [ ] Update prompts to use brand voice
- [ ] Add custom intro/outro injection
- [ ] Test: Same content, different brand voices

### Week 3: Distribution MVP
- [ ] Generate proper RSS feed
- [ ] Build Transistor/Buzzsprout integration
- [ ] Add "copy RSS link" for manual submission
- [ ] Test: Episode appears in Spotify

### Week 4: Onboarding + Auth
- [ ] Supabase auth setup
- [ ] Stripe billing integration
- [ ] Onboarding wizard UI
- [ ] Test: Complete user journey

---

## Quick Win: Newsletter-to-Podcast Demo

Build this ONE flow perfectly:

```
INPUT:  https://yoursubstack.substack.com/p/latest-post
OUTPUT: 6-minute podcast episode ready to publish

Demo script:
1. Paste Substack URL
2. Wait 2 minutes
3. Play professional podcast
4. "This is what PodcastOS does"
```

This is your Product Hunt launch demo.
This is your sales call closer.
This is your "aha moment."

---

## Revenue Projection

| Month | Customers | Avg Price | MRR |
|-------|-----------|-----------|-----|
| 1 | 20 | $79 | $1,580 |
| 2 | 50 | $89 | $4,450 |
| 3 | 100 | $99 | $9,900 |
| 4 | 150 | $119 | $17,850 |
| 5 | 200 | $129 | $25,800 |
| 6 | 300 | $139 | $41,700 |

**Path to $50K MRR in 6 months:**
- 300 customers
- Mix of $99 creators + $249 pro + $499 business
- Driven by: Product Hunt, Substack community, content marketing
