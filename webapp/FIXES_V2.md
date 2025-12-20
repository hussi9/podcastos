# Podcast Studio v2 - Issues & Fixes

## Summary
This document tracks all issues identified in v1 and their fixes in v2.

---

## Critical Issues (App Breaking)

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| 1 | Generation doesn't run - clicking Generate only creates DB record | FIXED | Added `threading.Thread` background runner with `asyncio` event loop |
| 2 | Missing template: `/profiles/{id}/edit` | FIXED | Created `profiles/edit.html` |
| 3 | Missing template: `/profiles/{id}/topics` | FIXED | Created `topics/list.html` |
| 4 | Missing template: `/episodes` | FIXED | Created `episodes/list.html` |
| 5 | Missing template: `/episodes/{id}` | FIXED | Created `episodes/detail.html` |
| 6 | Missing template: `/hosts/new` | FIXED | Created `hosts/new.html` |
| 7 | Missing template: `/hosts/{id}/edit` | FIXED | Created `hosts/edit.html` |
| 8 | Missing template: `/sources/list` | FIXED | Created `sources/list.html` |
| 9 | Missing template: `/sources/new` | FIXED | Created `sources/new.html` |
| 10 | Categories form serialization broken | FIXED | Changed to `request.form.getlist('categories')` |

---

## UX Issues

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| 11 | No audio player for episodes | FIXED | Added HTML5 audio player in episode detail |
| 12 | No download button | FIXED | Added `/episodes/{id}/download` route and button |
| 13 | No loading states on buttons | FIXED | Added JS loading state on form submit |
| 14 | No confirmation for delete actions | FIXED | Added `onclick="return confirm()"` |
| 15 | Can't edit hosts | FIXED | Added `/hosts/{id}/edit` route |
| 16 | Can't delete hosts | FIXED | Added `/hosts/{id}/delete` route |
| 17 | Can't delete sources | FIXED | Added `/sources/{id}/delete` route |
| 18 | Can't toggle sources on/off | FIXED | Added `/sources/{id}/toggle` route |
| 19 | No job cancel button | FIXED | Added `/jobs/{id}/cancel` route |
| 20 | Real-time status updates don't work | FIXED | Fixed polling with proper JSON API |

---

## Missing Features

| # | Feature | Status | Implementation |
|---|---------|--------|----------------|
| 21 | RSS feed generation | FIXED | Added `/profiles/{id}/feed.xml` route |
| 22 | Audio serving endpoint | FIXED | Added `/audio/{filename}` route |
| 23 | Episode delete with file cleanup | FIXED | Deletes WAV file when episode deleted |
| 24 | Profile delete | FIXED | Added with cascade delete |
| 25 | Topic avoidance delete | FIXED | Added remove from avoidance list |
| 26 | Voice selection dropdown | FIXED | Added 14 Gemini voices |
| 27 | Expertise areas as tags | FIXED | Comma-separated input |

---

## Templates Created/Updated

### New Templates (v2)
1. `profiles/edit.html` - Edit profile form
2. `topics/list.html` - Topic history and avoidance management
3. `episodes/list.html` - All episodes with pagination
4. `episodes/detail.html` - Episode detail with audio player
5. `hosts/new.html` - Add host form with voice selection
6. `hosts/edit.html` - Edit host form
7. `sources/list.html` - Content sources management
8. `sources/new.html` - Add source form
9. `feed.xml` - RSS podcast feed template

### Updated Templates (v2)
1. `dashboard.html` - Fixed this_week_count variable
2. `profiles/new.html` - Fixed categories checkboxes
3. `generate/status.html` - Fixed polling and stage display

---

## Routes Added (v2)

```
GET/POST /profiles/{id}/edit          - Edit profile
POST     /profiles/{id}/delete        - Delete profile

GET/POST /profiles/{id}/hosts/new     - Add host
GET/POST /profiles/{id}/hosts/{id}/edit   - Edit host
POST     /profiles/{id}/hosts/{id}/delete - Delete host

GET      /profiles/{id}/topics        - Topic history
POST     /profiles/{id}/topics/avoid  - Add topic to avoid
POST     /profiles/{id}/topics/avoid/{id}/delete - Remove from avoid

GET      /profiles/{id}/sources       - List sources
GET/POST /profiles/{id}/sources/new   - Add source
POST     /profiles/{id}/sources/{id}/delete - Delete source
POST     /profiles/{id}/sources/{id}/toggle - Toggle active

GET      /episodes                    - All episodes
GET      /episodes/{id}               - Episode detail
GET      /episodes/{id}/download      - Download audio
POST     /episodes/{id}/delete        - Delete episode

POST     /jobs/{id}/cancel            - Cancel job

GET      /profiles/{id}/feed.xml      - RSS feed
GET      /audio/{filename}            - Serve audio files
```

---

## Background Job System

### v1 Problem
- `GenerationJob` record created but no actual processing
- No async/threading implementation

### v2 Solution
```python
# Start background thread
thread = threading.Thread(
    target=run_generation_async,
    args=(job_id, profile_id, options)
)
thread.daemon = True
thread.start()

# Thread creates new event loop for async code
def run_generation_async(job_id, profile_id, options):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_generation_pipeline(...))
```

### Pipeline Stages
1. `content_gathering` - Fetch Reddit, RSS, Google News
2. `research` - Deep research with Gemini (optional)
3. `scripting` - Generate dialogue with Gemini
4. `review` - Editorial review (optional)
5. `audio` - TTS with Gemini multi-speaker

---

## Database Changes

No schema changes required. All models from v1 are compatible.

---

## Testing Checklist

- [x] Create new profile (Route: /profiles/new - 200 OK)
- [x] Edit existing profile (Route: /profiles/{id}/edit - 200 OK)
- [x] Delete profile (Route: /profiles/{id}/delete - POST)
- [x] Add host with voice selection (Route: /profiles/{id}/hosts/new - 200 OK)
- [x] Edit host (Route: /profiles/{id}/hosts/{id}/edit)
- [x] Delete host (Route: /profiles/{id}/hosts/{id}/delete - POST)
- [x] Add content source (Route: /profiles/{id}/sources/new - 200 OK)
- [x] Toggle source active/inactive (Route: /profiles/{id}/sources/{id}/toggle - POST)
- [x] Delete source (Route: /profiles/{id}/sources/{id}/delete - POST)
- [x] Add topic to avoidance list (Route: /profiles/{id}/topics/avoid - POST)
- [x] Remove topic from avoidance (Route: /profiles/{id}/topics/avoid/{id}/delete - POST)
- [x] Start generation job (Route: /profiles/{id}/generate - POST triggers background thread)
- [x] Monitor job progress (Route: /jobs/{job_id} with API polling)
- [x] Cancel running job (Route: /jobs/{id}/cancel - POST)
- [x] View completed episode (Route: /episodes/{id} - 200 OK)
- [x] Play audio in browser (HTML5 audio player in episode detail)
- [x] Download audio file (Route: /episodes/{id}/download)
- [x] Delete episode (Route: /episodes/{id}/delete - POST)
- [x] Access RSS feed (Route: /profiles/{id}/feed.xml - 200 OK)

---

## Known Limitations (v2)

1. **No scheduled generation** - Must manually trigger
2. **No voice preview** - Can't hear voice samples
3. **No episode analytics** - No play counts
4. **SQLite only** - Not production-ready for scale
5. **No user authentication** - Open access
6. **Single server** - No horizontal scaling

---

## Future Improvements (v3)

1. Add user authentication
2. Add scheduled generation (cron)
3. Migrate to PostgreSQL
4. Add Celery for job queue
5. Add voice preview audio samples
6. Add episode analytics/stats
7. Add Spotify/Apple podcast integration
8. Add dark mode
9. Add mobile-responsive improvements
