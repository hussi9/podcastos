# Desi Daily - Podcast Distribution Guide

## Quick Start Checklist

- [ ] Create podcast cover art (3000x3000px)
- [ ] Sign up for Spotify for Podcasters
- [ ] Upload first episode
- [ ] Submit to Apple Podcasts
- [ ] Set up automated uploads

---

## Step 1: Create Podcast Cover Art

Use one of these free tools:
- **Canva**: https://www.canva.com/create/podcast-covers/
- **Adobe Express**: https://www.adobe.com/express/create/podcast-cover

Requirements:
- 3000x3000 pixels (square)
- JPG or PNG format
- Under 512KB file size
- No explicit imagery

See `assets/cover-art-spec.md` for design ideas.

---

## Step 2: Set Up Spotify for Podcasters

### 2.1 Create Account
1. Go to: https://podcasters.spotify.com/
2. Sign in with your Spotify account (or create one)
3. Click "Get Started"

### 2.2 Create New Podcast
1. Click "New Podcast" or "Create a Podcast"
2. Fill in podcast details:

**Podcast Name**: `Desi Daily`

**Description**:
```
Your daily dose of news and insights for the South Asian community in America.

Join hosts Raj and Priya as they discuss the latest on immigration (H-1B, Green Cards, USCIS updates), career opportunities, community news, and cultural topics that matter to desi immigrants.

New episodes every day at 6 AM EST.

Topics we cover:
- H-1B visa news and updates
- Green card backlog and priority dates
- USCIS policy changes
- Career and job market insights
- Community stories and cultural discussions
- Family and relationship topics

Subscribe and never miss an episode!
```

**Category**: News > Daily News
**Language**: English
**Explicit**: No

### 2.3 Upload Cover Art
- Upload your 3000x3000px cover image

### 2.4 Upload First Episode
1. Click "New Episode"
2. Upload: `output/audio/dd-20251213-full.mp3`
3. Episode details:
   - **Title**: H-1B Visa Updates | Desi Daily - Dec 13
   - **Description**: (copy from script JSON)
   - **Season**: 1
   - **Episode**: 1

---

## Step 3: Distribute to Other Platforms

### Apple Podcasts
1. From Spotify for Podcasters dashboard
2. Go to "Distribution" or "Availability"
3. Click "Get listed on Apple Podcasts"
4. Follow the prompts (may need Apple Podcasts Connect account)

**OR manually:**
1. Go to: https://podcastsconnect.apple.com/
2. Sign in with Apple ID
3. Click "+" to add new show
4. Enter your RSS feed URL from Spotify for Podcasters
5. Wait 24-48 hours for approval

### Other Platforms (automatic via Spotify for Podcasters)
- Amazon Music / Audible
- iHeartRadio
- Pandora
- Deezer
- PlayerFM

---

## Step 4: Automated Episode Uploads

### Option A: Manual Daily Upload
Run the podcast engine daily and manually upload to Spotify for Podcasters.

### Option B: RSS Feed (Recommended)
1. Host audio files on your own server/S3
2. Use the generated RSS feed (`output/feed.xml`)
3. Point Spotify for Podcasters to your RSS URL
4. New episodes auto-sync!

### Setting Up Self-Hosted RSS
1. Upload audio to Supabase Storage or S3
2. Update `config/settings.py` with public URLs
3. RSS feed auto-updates with new episodes

---

## Podcast Details for Submission

**Podcast Name**: Desi Daily
**Author**: DesiVibe
**Email**: podcast@desivibe.com (update this)
**Website**: https://desivibe.com/podcast
**Category**: News > Daily News
**Subcategory**: Society & Culture > Places & Travel
**Language**: English (United States)
**Explicit**: No

**Short Description** (max 255 chars):
```
Daily news and insights for South Asian immigrants in America. H-1B updates, green card news, career tips, and community stories with hosts Raj and Priya.
```

**Long Description**:
```
Desi Daily is your go-to podcast for staying informed about everything that matters to the South Asian community in the United States.

Every day, hosts Raj and Priya bring you the latest updates on:

🛂 Immigration News
- H-1B visa updates and policy changes
- Green card backlog and priority date movements
- USCIS announcements and processing times
- F-1/OPT student visa information

💼 Career & Professional
- Job market trends for immigrants
- Tech industry news
- Professional development tips

🏠 Community & Culture
- Stories from the desi community
- Cultural events and celebrations
- Family and relationship discussions

Raj brings his 10+ years of experience as an immigrant tech professional, offering practical advice and insider knowledge. Priya adds cultural context and community perspectives as a second-generation Indian-American.

New episodes drop every morning at 6 AM EST. Subscribe now and start your day informed!

#DesiDaily #SouthAsian #Immigration #H1B #GreenCard #IndianAmerican #Podcast
```

---

## Marketing Tips

### Social Media
- Create accounts: @DesiDailyPod on Twitter/X, Instagram, LinkedIn
- Share daily episode clips (30-60 seconds)
- Engage with immigration and desi community hashtags

### SEO Keywords
- Desi podcast
- Indian American podcast
- H1B visa podcast
- Immigration news podcast
- South Asian podcast
- Green card podcast

### Cross-Promotion
- Share in relevant subreddits (r/ABCDesis, r/h1b, r/immigration)
- Post in Facebook groups for Indian immigrants
- LinkedIn articles about episode topics

---

## Support

For technical issues with the podcast engine:
- Check logs in `output/logs/`
- Run `python scheduler.py --preview` to test

For distribution issues:
- Spotify Support: https://support.spotify.com/podcasters
- Apple Podcasts: https://help.apple.com/itc/podcasts/
