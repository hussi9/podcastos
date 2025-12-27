"""
Podcast Production Studio - Web Application v2
A comprehensive webapp for managing podcast generation workflows.
"""

import os
import sys
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import desc
from sqlalchemy.orm import sessionmaker, joinedload

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp.models import (
    Base, PodcastProfile, Host, Episode, TopicHistory,
    TopicAvoidance, ContentSource, GenerationJob, AppSettings,
    Newsletter, init_db
)
from webapp.services.generation_service import GenerationService
from src.intelligence.synthesis.content_engine import ContentEngine, ContentInput
import asyncio
from flask import send_from_directory

# Import wizard API
from webapp.wizard_api import wizard_api

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'podcast-studio-dev-key-v2')

# CSRF Protection
csrf = CSRFProtect(app)

# Rate Limiting
from webapp.rate_limiter import add_rate_limit_headers, generation_rate_limit, api_rate_limit

@app.after_request
def after_request_rate_limit(response):
    """Add rate limit headers to all responses."""
    return add_rate_limit_headers(response)

# Register blueprints
app.register_blueprint(wizard_api)

# Database setup
DB_PATH = Path(__file__).parent / 'podcast_studio.db'
engine = init_db(str(DB_PATH))
Session = sessionmaker(bind=engine)

# Initialize Services
# We pass the Session factory, not an instance, so the service can manage its own threads/scopes
gen_service = GenerationService(Session)

# Available TTS voices (Gemini TTS)
AVAILABLE_VOICES = [
    'Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede', 'Leda', 'Orus', 'Zephyr',
    'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba'
]


def get_db():
    """Get database session."""
    return Session()


def safe_int(value, default=0, min_val=None, max_val=None):
    """Safely convert a value to integer with bounds checking."""
    try:
        result = int(value) if value else default
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)
        return result
    except (ValueError, TypeError):
        return default


def validate_string(value, max_length=255, default=''):
    """Validate and truncate string input."""
    if not value:
        return default
    value = str(value).strip()
    if len(value) > max_length:
        value = value[:max_length]
    return value


def validate_url(url: str) -> bool:
    """Validate a URL format."""
    from urllib.parse import urlparse
    if not url:
        return False
    try:
        result = urlparse(url)
        return result.scheme in ('http', 'https') and bool(result.netloc)
    except Exception:
        return False


# ============================================================
# ROUTES - Dashboard
# ============================================================

# ============================================================
# ROUTES - Public & Auth
# ============================================================

@app.route('/')
def dashboard():
    """Main dashboard showing all profiles and recent activity."""
    db = get_db()
    try:
        profiles = db.query(PodcastProfile).filter_by(is_active=True).all()
        recent_episodes = db.query(Episode).options(
            joinedload(Episode.profile)
        ).order_by(desc(Episode.created_at)).limit(10).all()

        # Clean up stale jobs (stuck in pending/running for > 10 minutes with < 5% progress)
        from datetime import datetime, timedelta
        stale_threshold = datetime.utcnow() - timedelta(minutes=10)
        stale_jobs = db.query(GenerationJob).filter(
            GenerationJob.status.in_(['running', 'pending']),
            GenerationJob.progress_percent < 5,
            GenerationJob.created_at < stale_threshold
        ).all()
        for job in stale_jobs:
            job.status = 'failed'
            job.error_message = 'Job timed out - no progress detected'
        if stale_jobs:
            db.commit()

        running_jobs_db = db.query(GenerationJob).filter(
            GenerationJob.status.in_(['running', 'pending'])
        ).all()

        # Count newsletters
        newsletter_count = db.query(Newsletter).count()

        # Count total episodes
        total_episodes = db.query(Episode).count()

        # Check if API keys are configured
        needs_setup = not os.getenv('GEMINI_API_KEY')

        return render_template('dashboard.html',
            profiles=profiles,
            recent_episodes=recent_episodes,
            running_jobs=running_jobs_db,
            newsletter_count=newsletter_count,
            total_episodes=total_episodes,
            needs_setup=needs_setup
        )
    finally:
        db.close()

@app.route('/files/<path:filename>')
def serve_files(filename):
    """Serve generated files from output directory."""
    return send_from_directory(Path(__file__).parent.parent / 'output', filename)




# ============================================================
# ROUTES - Studio Dashboard
# ============================================================




# ============================================================
# ROUTES - Podcast Profiles
# ============================================================

@app.route('/profiles')
def profiles_list():
    """List all podcast profiles."""
    db = get_db()
    try:
        profiles = db.query(PodcastProfile).all()
        return render_template('profiles/list.html', profiles=profiles)
    finally:
        db.close()


@app.route('/profiles/new', methods=['GET', 'POST'])
def profile_new():
    """Create a new podcast profile."""
    if request.method == 'POST':
        db = get_db()
        try:
            # Validate required field
            name = validate_string(request.form.get('name'), max_length=100)
            if not name:
                flash('Profile name is required', 'error')
                return render_template('profiles/new.html')

            # Parse and validate other fields
            categories = request.form.getlist('categories')[:10]  # Limit to 10 categories

            profile = PodcastProfile(
                name=name,
                description=validate_string(request.form.get('description'), max_length=1000),
                target_audience=validate_string(request.form.get('target_audience'), max_length=500),
                tone=validate_string(request.form.get('tone'), max_length=50, default='conversational'),
                language=validate_string(request.form.get('language'), max_length=10, default='en-US'),
                target_duration_minutes=safe_int(request.form.get('duration'), default=10, min_val=5, max_val=60),
                topic_count=safe_int(request.form.get('topic_count'), default=5, min_val=1, max_val=20),
                categories=categories,
            )
            db.add(profile)
            db.commit()
            flash(f'Profile "{profile.name}" created successfully!', 'success')
            return redirect(url_for('profile_detail', profile_id=profile.id))
        except Exception as e:
            db.rollback()
            flash(f'Error creating profile: {str(e)}', 'error')
        finally:
            db.close()

    return render_template('profiles/new.html')


@app.route('/profiles/<int:profile_id>')
def profile_detail(profile_id):
    """View podcast profile details."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).options(
            joinedload(PodcastProfile.hosts),
            joinedload(PodcastProfile.sources)
        ).get(profile_id)
        if not profile:
            flash('Profile not found', 'error')
            return redirect(url_for('profiles_list'))

        episodes = db.query(Episode).filter_by(profile_id=profile_id).order_by(desc(Episode.date)).limit(20).all()
        avoided_topics = db.query(TopicAvoidance).filter_by(profile_id=profile_id, is_active=True).all()

        return render_template('profiles/detail.html',
            profile=profile,
            episodes=episodes,
            avoided_topics=avoided_topics
        )
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/edit', methods=['GET', 'POST'])
def profile_edit(profile_id):
    """Edit podcast profile."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            flash('Profile not found', 'error')
            return redirect(url_for('profiles_list'))

        if request.method == 'POST':
            # Use safe_int for all integer conversions to prevent ValueError
            profile.name = validate_string(request.form.get('name', ''), max_length=100, default=profile.name)
            profile.description = validate_string(request.form.get('description', ''), max_length=1000)
            profile.target_audience = validate_string(request.form.get('target_audience', ''), max_length=200)
            profile.tone = validate_string(request.form.get('tone', 'conversational'), max_length=50)
            profile.language = validate_string(request.form.get('language', 'en-US'), max_length=10)
            profile.target_duration_minutes = safe_int(request.form.get('duration'), default=10, min_val=1, max_val=120)
            profile.topic_count = safe_int(request.form.get('topic_count'), default=5, min_val=1, max_val=20)
            profile.categories = request.form.getlist('categories')

            # Handle scheduling fields with safe_int
            schedule_was_enabled = profile.schedule_enabled
            profile.schedule_enabled = 'schedule_enabled' in request.form
            profile.schedule_hour = safe_int(request.form.get('schedule_hour'), default=6, min_val=0, max_val=23)
            profile.schedule_minute = safe_int(request.form.get('schedule_minute'), default=0, min_val=0, max_val=59)
            profile.schedule_days = request.form.getlist('schedule_days') or ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            profile.timezone = request.form.get('timezone', 'America/New_York')

            db.commit()

            # Update scheduler if schedule changed
            try:
                from webapp.scheduler import update_profile_schedule
                update_profile_schedule(profile_id)
                if profile.schedule_enabled and not schedule_was_enabled:
                    flash('Profile updated and scheduling enabled!', 'success')
                elif not profile.schedule_enabled and schedule_was_enabled:
                    flash('Profile updated and scheduling disabled.', 'success')
                else:
                    flash('Profile updated successfully!', 'success')
            except Exception as e:
                flash(f'Profile updated but scheduler error: {e}', 'warning')

            return redirect(url_for('profile_detail', profile_id=profile_id))

        return render_template('profiles/edit.html', profile=profile)
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/delete', methods=['POST'])
def profile_delete(profile_id):
    """Delete a podcast profile."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if profile:
            db.delete(profile)
            db.commit()
            flash(f'Profile "{profile.name}" deleted', 'success')
    finally:
        db.close()
    return redirect(url_for('profiles_list'))


# ============================================================
# ROUTES - Hosts
# ============================================================

@app.route('/profiles/<int:profile_id>/hosts/new', methods=['GET', 'POST'])
def host_new(profile_id):
    """Add a new host to a profile."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            flash('Profile not found', 'error')
            return redirect(url_for('profiles_list'))

        if request.method == 'POST':
            # Validate host name
            name = validate_string(request.form.get('name'), max_length=50)
            if not name:
                flash('Host name is required', 'error')
                return render_template('hosts/new.html', profile=profile, voices=AVAILABLE_VOICES)

            # Validate voice is in allowed list
            voice_name = request.form.get('voice_name', 'Puck')
            if voice_name not in AVAILABLE_VOICES:
                voice_name = 'Puck'

            # Parse expertise with limit
            expertise_raw = request.form.get('expertise_areas', '')
            expertise = [validate_string(x, max_length=100) for x in expertise_raw.split(',') if x.strip()][:10]

            host = Host(
                profile_id=profile_id,
                name=name,
                persona=validate_string(request.form.get('persona'), max_length=1000),
                voice_name=voice_name,
                speaking_style=validate_string(request.form.get('speaking_style'), max_length=500),
                expertise_areas=expertise,
            )
            db.add(host)
            db.commit()
            flash(f'Host "{host.name}" added!', 'success')
            return redirect(url_for('profile_detail', profile_id=profile_id))

        return render_template('hosts/new.html', profile=profile, voices=AVAILABLE_VOICES)
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/hosts/<int:host_id>/edit', methods=['GET', 'POST'])
def host_edit(profile_id, host_id):
    """Edit a host."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        host = db.query(Host).get(host_id)

        if not profile or not host:
            flash('Not found', 'error')
            return redirect(url_for('profiles_list'))

        if request.method == 'POST':
            host.name = request.form['name']
            host.persona = request.form.get('persona', '')
            host.voice_name = request.form.get('voice_name', 'Puck')
            host.speaking_style = request.form.get('speaking_style', '')
            host.expertise_areas = [x.strip() for x in request.form.get('expertise_areas', '').split(',') if x.strip()]
            db.commit()
            flash('Host updated!', 'success')
            return redirect(url_for('profile_detail', profile_id=profile_id))

        return render_template('hosts/edit.html', profile=profile, host=host, voices=AVAILABLE_VOICES)
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/hosts/<int:host_id>/delete', methods=['POST'])
def host_delete(profile_id, host_id):
    """Delete a host."""
    db = get_db()
    try:
        host = db.query(Host).get(host_id)
        if host:
            db.delete(host)
            db.commit()
            flash('Host deleted', 'success')
    finally:
        db.close()
    return redirect(url_for('profile_detail', profile_id=profile_id))


# ============================================================
# ROUTES - Topic Management
# ============================================================

@app.route('/profiles/<int:profile_id>/topics')
def topics_list(profile_id):
    """View topic history for a profile."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            flash('Profile not found', 'error')
            return redirect(url_for('profiles_list'))

        # Get recent topics
        recent_topics = db.query(TopicHistory).join(Episode).filter(
            Episode.profile_id == profile_id
        ).order_by(desc(TopicHistory.created_at)).limit(50).all()

        # Get avoided topics
        avoided = db.query(TopicAvoidance).filter_by(profile_id=profile_id, is_active=True).all()

        return render_template('topics/list.html',
            profile=profile,
            recent_topics=recent_topics,
            avoided_topics=avoided
        )
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/topics/avoid', methods=['POST'])
def topic_avoid(profile_id):
    """Add a topic to the avoidance list."""
    db = get_db()
    try:
        avoidance = TopicAvoidance(
            profile_id=profile_id,
            keyword=request.form['keyword'],
            reason=request.form.get('reason', ''),
            avoidance_type=request.form.get('avoidance_type', 'temporary'),
            min_days_between=int(request.form.get('min_days', 7)),
        )

        if request.form.get('avoid_until'):
            avoidance.avoid_until = datetime.fromisoformat(request.form['avoid_until'])

        db.add(avoidance)
        db.commit()
        flash(f'Topic "{avoidance.keyword}" added to avoidance list', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'error')
    finally:
        db.close()

    return redirect(url_for('topics_list', profile_id=profile_id))


@app.route('/profiles/<int:profile_id>/topics/avoid/<int:avoid_id>/delete', methods=['POST'])
def topic_avoid_delete(profile_id, avoid_id):
    """Remove topic from avoidance list."""
    db = get_db()
    try:
        avoidance = db.query(TopicAvoidance).get(avoid_id)
        if avoidance:
            db.delete(avoidance)
            db.commit()
            flash('Topic removed from avoidance list', 'success')
    finally:
        db.close()
    return redirect(url_for('topics_list', profile_id=profile_id))


# ============================================================
# ROUTES - Content Sources
# ============================================================

@app.route('/profiles/<int:profile_id>/sources')
def sources_list(profile_id):
    """View and manage content sources."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        sources = db.query(ContentSource).filter_by(profile_id=profile_id).order_by(desc(ContentSource.priority)).all()

        return render_template('sources/list.html', profile=profile, sources=sources)
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/sources/new', methods=['GET', 'POST'])
def source_new(profile_id):
    """Add a new content source."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)

        if request.method == 'POST':
            from src.utils.validation import validate_string, validate_url, safe_int
            
            config = {}
            source_type = validate_string(request.form.get('source_type', ''), max_length=50)
            
            if not source_type:
                flash('Source type is required', 'error')
                return render_template('sources/new.html', profile=profile)

            if source_type == 'reddit':
                subreddit = validate_string(request.form.get('subreddit', ''), max_length=50)
                if subreddit:
                    # Remove r/ prefix if present
                    subreddit = subreddit.lstrip('r/').strip()
                config['subreddit'] = subreddit
            elif source_type == 'rss':
                rss_url = request.form.get('rss_url', '').strip()
                if rss_url and not validate_url(rss_url):
                    flash('Invalid RSS URL format. Must be a valid HTTP/HTTPS URL.', 'error')
                    return render_template('sources/new.html', profile=profile)
                config['url'] = rss_url
            elif source_type == 'google_news':
                config['query'] = validate_string(request.form.get('search_query', ''), max_length=200)

            source_name = validate_string(request.form.get('name', ''), max_length=100)
            if not source_name:
                flash('Source name is required', 'error')
                return render_template('sources/new.html', profile=profile)

            source = ContentSource(
                profile_id=profile_id,
                name=source_name,
                source_type=source_type,
                config=config,
                priority=safe_int(request.form.get('priority'), default=5, min_val=1, max_val=10),
                categories=[x.strip() for x in request.form.get('categories', '').split(',') if x.strip()],
            )
            db.add(source)
            db.commit()
            flash(f'Source "{source.name}" added!', 'success')
            return redirect(url_for('sources_list', profile_id=profile_id))

        return render_template('sources/new.html', profile=profile)
    finally:
        db.close()


@app.route('/profiles/<int:profile_id>/sources/<int:source_id>/delete', methods=['POST'])
def source_delete(profile_id, source_id):
    """Delete a content source."""
    db = get_db()
    try:
        source = db.query(ContentSource).get(source_id)
        if source:
            db.delete(source)
            db.commit()
            flash('Source deleted', 'success')
    finally:
        db.close()
    return redirect(url_for('sources_list', profile_id=profile_id))


@app.route('/profiles/<int:profile_id>/sources/<int:source_id>/toggle', methods=['POST'])
def source_toggle(profile_id, source_id):
    """Toggle source active status."""
    db = get_db()
    try:
        source = db.query(ContentSource).get(source_id)
        if source:
            source.is_active = not source.is_active
            db.commit()
    finally:
        db.close()
    return redirect(url_for('sources_list', profile_id=profile_id))


# ============================================================
# ROUTES - Episodes
# ============================================================

@app.route('/episodes')
def episodes_list():
    """List all episodes across profiles."""
    db = get_db()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        episodes = db.query(Episode).options(
            joinedload(Episode.profile)
        ).order_by(desc(Episode.date)).limit(per_page).offset((page-1)*per_page).all()
        total = db.query(Episode).count()

        return render_template('episodes/list.html',
            episodes=episodes,
            page=page,
            total=total,
            per_page=per_page
        )
    finally:
        db.close()


@app.route('/episodes/<int:episode_id>')
def episode_detail(episode_id):
    """View episode details."""
    db = get_db()
    try:
        episode = db.query(Episode).get(episode_id)
        if not episode:
            flash('Episode not found', 'error')
            return redirect(url_for('episodes_list'))

        profile = db.query(PodcastProfile).get(episode.profile_id)
        topics = db.query(TopicHistory).filter_by(episode_id=episode_id).all()

        return render_template('episodes/detail.html',
            episode=episode,
            profile=profile,
            topics=topics,
            has_research=(Path(__file__).parent.parent / 'output' / 'scripts' / f"{episode.episode_id}_research.json").exists()
        )
    finally:
        db.close()


@app.route('/player/<int:episode_id>')
def mobile_player(episode_id):
    """Mobile-first interactive player prototype."""
    # We just serve the shell; the React app fetches data from the API
    return render_template('player/mobile.html', episode_id=episode_id)


@app.route('/api/episodes/<int:episode_id>')
def api_get_episode(episode_id):
    """Get episode details + segment manifest (for interactive player)."""
    db = get_db()
    try:
        episode = db.query(Episode).get(episode_id)
        if not episode:
            return jsonify({'error': 'Episode not found'}), 404
            
        return jsonify({
            'id': episode.id,
            'title': episode.title,
            'date': episode.date.isoformat(),
            'audio_url': url_for('serve_audio', filename=Path(episode.audio_path).name) if episode.audio_path else None,
            'segments': [
                {
                    'sequence': s.sequence_index,
                    'title': s.title,
                    'topic_id': s.topic_id,
                    'audio_url': url_for('serve_audio', filename=f"{episode.episode_id}/{Path(s.audio_path).name}") if s.audio_path else None,
                    'duration': s.duration_seconds
                }
                for s in episode.segments
            ]
        })
    finally:
        db.close()


@app.route('/episodes/<int:episode_id>/download')
def episode_download(episode_id):
    """Download episode audio file."""
    db = get_db()
    try:
        episode = db.query(Episode).get(episode_id)
        if not episode or not episode.audio_path:
            flash('Audio file not found', 'error')
            return redirect(url_for('episodes_list'))

        audio_path = Path(episode.audio_path)
        if not audio_path.exists():
            flash('Audio file not found on disk', 'error')
            return redirect(url_for('episode_detail', episode_id=episode_id))

        return send_file(
            audio_path,
            as_attachment=True,
            download_name=f"{episode.episode_id}.wav"
        )
    finally:
        db.close()


@app.route('/newsletters')
def newsletters_list():
    """List all newsletters."""
    db = get_db()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        newsletters = db.query(Newsletter).options(
            joinedload(Newsletter.episode),
            joinedload(Newsletter.profile)
        ).order_by(desc(Newsletter.issue_date)).limit(per_page).offset((page-1)*per_page).all()
        total = db.query(Newsletter).count()

        return render_template('newsletters/list.html',
            newsletters=newsletters,
            page=page,
            total=total,
            per_page=per_page
        )
    finally:
        db.close()


@app.route('/episodes/<int:episode_id>/generate_newsletter', methods=['POST'])
def episode_generate_newsletter(episode_id):
    """Manually trigger newsletter generation for an episode."""
    db = get_db()
    try:
        episode = db.query(Episode).get(episode_id)
        if not episode:
            flash('Episode not found', 'error')
            return redirect(url_for('episodes_list'))
            
        # Check for research
        research_path = Path(__file__).parent.parent / 'output' / 'scripts' / f"{episode.episode_id}_research.json"
        if not research_path.exists():
            flash('No research data found for this episode. Cannot generate newsletter.', 'error')
            return redirect(url_for('episode_detail', episode_id=episode_id))

        # Run generation (async/threaded)
        try:
             # We use a simplified thread here since we don't have a full job context, 
             # or we could create a dummy job. For now, let's run it and flash.
             # Better: create a lightweight job? 
             # For simplicity in this "studio" pivot, we'll just spawn the service method in a thread.
             
             import threading
             def run_gen():
                 loop = asyncio.new_event_loop()
                 asyncio.set_event_loop(loop)
                 try:
                     # Re-init engine to get paths
                     from src.podcast_engine import PodcastEngine
                     import os
                     engine = PodcastEngine(
                        gemini_api_key=os.getenv("GEMINI_API_KEY"),
                        output_dir="output"
                     )
                     
                     loop.run_until_complete(gen_service._generate_and_save_newsletter(
                         episode.profile_id, 
                         engine, 
                         episode.episode_id, 
                         episode.id, 
                         "Deep Dive Weekly" # Default name
                     ))
                 except Exception as e:
                     print(f"Error generating newsletter: {e}")
                 finally:
                     loop.close()

             t = threading.Thread(target=run_gen, daemon=True)
             t.start()
             
             flash('Newsletter generation started in background...', 'success')
        except Exception as e:
            flash(f'Failed to start generation: {e}', 'error')
            
        return redirect(url_for('episode_detail', episode_id=episode_id))
    finally:
        db.close()


@app.route('/newsletters/<int:id>')
def newsletter_detail(id):
    """View generated newsletter."""
    db = get_db()
    try:
        # Check if ID is for newsletter or episode
        newsletter = db.query(Newsletter).get(id)
        if not newsletter:
            # Fallback: try to find by episode_id
            newsletter = db.query(Newsletter).filter_by(episode_id=id).first()

        if not newsletter:
            flash("Newsletter not found", "error")
            return redirect(url_for('newsletters_list'))

        # Get profile for the masthead
        profile = db.query(PodcastProfile).get(newsletter.profile_id) if newsletter.profile_id else None

        return render_template('newsletters/detail.html', newsletter=newsletter, profile=profile)
    finally:
        db.close()


@app.route('/api/newsletters/<int:newsletter_id>/generate-images', methods=['POST'])
def generate_newsletter_images(newsletter_id):
    """Generate AI images for newsletter sections using Gemini Imagen."""
    import google.generativeai as genai
    from pathlib import Path
    import base64
    import uuid

    db = get_db()
    try:
        newsletter = db.query(Newsletter).get(newsletter_id)
        if not newsletter:
            return jsonify({'error': 'Newsletter not found'}), 404

        # Get API key
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'error': 'GEMINI_API_KEY not configured'}), 500

        genai.configure(api_key=api_key)

        # Get profile for context
        profile = db.query(PodcastProfile).get(newsletter.profile_id) if newsletter.profile_id else None
        profile_context = profile.name if profile else "Newsletter"

        # Ensure output directory exists
        images_dir = Path('webapp/static/newsletter_images')
        images_dir.mkdir(parents=True, exist_ok=True)

        # Update sections with generated images
        updated_sections = []
        sections = newsletter.sections or []

        for i, section in enumerate(sections):
            if section.get('image_url'):
                # Already has image
                updated_sections.append(section)
                continue

            try:
                # Create a prompt for the image
                headline = section.get('headline', 'News Story')
                body_preview = (section.get('body', '')[:200] + '...') if section.get('body') else ''

                image_prompt = f"""Create a professional, editorial-style illustration for a news article.

Topic: {headline}
Context: {body_preview}
Style: Modern, clean, professional news publication illustration. Think New York Times or The Economist style.
- Use a sophisticated color palette
- Abstract or symbolic representation preferred over literal depiction
- High contrast, visually striking
- Suitable for a professional newsletter header

Do NOT include any text, logos, or watermarks in the image."""

                # Use Gemini's image generation (Imagen 3)
                try:
                    imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-002")
                    result = imagen_model.generate_images(
                        prompt=image_prompt,
                        number_of_images=1,
                        aspect_ratio="16:9",
                        safety_filter_level="block_only_high",
                    )

                    if result.images:
                        # Save image
                        image_filename = f"newsletter_{newsletter_id}_section_{i}_{uuid.uuid4().hex[:8]}.png"
                        image_path = images_dir / image_filename

                        # Save the image bytes
                        result.images[0].save(str(image_path))

                        # Update section with image URL
                        section['image_url'] = f'/static/newsletter_images/{image_filename}'
                        section['image_caption'] = f'AI-generated illustration for: {headline}'

                except Exception as img_error:
                    # Fallback: Use placeholder or skip
                    print(f"Image generation failed for section {i}: {img_error}")
                    # Use a gradient placeholder
                    section['image_url'] = None

            except Exception as e:
                print(f"Error processing section {i}: {e}")

            updated_sections.append(section)

        # Save updated sections
        newsletter.sections = updated_sections
        db.commit()

        return jsonify({
            'success': True,
            'message': f'Generated images for {len([s for s in updated_sections if s.get("image_url")])} sections',
            'newsletter_id': newsletter_id
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/episodes/<int:episode_id>/delete', methods=['POST'])
def episode_delete(episode_id):
    """Delete an episode."""
    db = get_db()
    try:
        episode = db.query(Episode).get(episode_id)
        if episode:
            # Delete audio file if exists
            if episode.audio_path:
                audio_path = Path(episode.audio_path)
                if audio_path.exists():
                    audio_path.unlink()
            db.delete(episode)
            db.commit()
            flash('Episode deleted', 'success')
    finally:
        db.close()
    return redirect(url_for('episodes_list'))


# ============================================================
# ROUTES - Generation Pipeline
# ============================================================

@app.route('/profiles/<int:profile_id>/generate', methods=['GET', 'POST'])
@generation_rate_limit
def generate_episode(profile_id):
    """Start podcast generation (rate limited: 5/minute)."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            flash('Profile not found', 'error')
            return redirect(url_for('profiles_list'))

        if request.method == 'POST':
            # Extract options
            options = {
                'topic_count': int(request.form.get('topic_count', profile.topic_count)),
                'duration': int(request.form.get('duration', profile.target_duration_minutes)),
                'deep_research': 'deep_research' in request.form,
                'use_continuity': 'use_continuity' in request.form,
                'editorial_review': 'editorial_review' in request.form,
                'tts_model': request.form.get('tts_model', 'gemini-2.5-flash-preview-tts'),
                'focus': request.form.get('focus', ''),
            }

            # Use Service to start job
            try:
                job_id = gen_service.start_generation_job(profile_id, options)
                flash(f'Generation job {job_id} started!', 'success')
                return redirect(url_for('job_status', job_id=job_id))
            except Exception as e:
                flash(f'Failed to start job: {str(e)}', 'error')
                return redirect(url_for('profile_detail', profile_id=profile_id))

        # GET - show generation options
        return render_template('generate/options.html', profile=profile)
    finally:
        db.close()


@app.route('/jobs')
def jobs_list():
    """List all generation jobs."""
    db = get_db()
    try:
        status_filter = request.args.get('status')

        query = db.query(GenerationJob).order_by(desc(GenerationJob.created_at))

        if status_filter:
            query = query.filter_by(status=status_filter)

        jobs = query.limit(100).all()

        return render_template('jobs/list.html',
            jobs=jobs,
            status_filter=status_filter
        )
    finally:
        db.close()


@app.route('/jobs/<job_id>')
def job_status(job_id):
    """View generation job status."""
    db = get_db()
    try:
        job = db.query(GenerationJob).filter_by(job_id=job_id).first()
        if not job:
            flash('Job not found', 'error')
            return redirect(url_for('dashboard'))

        # If waiting for review, redirect to review page
        if job.status == 'waiting_for_review':
            return redirect(url_for('job_review', job_id=job_id))

        if job.status == 'completed' and job.episode_id:
             # Optional: Redirect to episode if done? 
             # For now keep status page so they see "Done"
             pass

        profile = db.query(PodcastProfile).get(job.profile_id)
        return render_template('generate/status.html', job=job, profile=profile)
    finally:
        db.close()


@app.route('/jobs/<job_id>/review')
def job_review(job_id):
    """Review generated script."""
    db = get_db()
    try:
        job = db.query(GenerationJob).filter_by(job_id=job_id).first()
        if not job:
            return redirect(url_for('dashboard'))
            
        if job.status != 'waiting_for_review':
            flash('Job is not in review state', 'warning')
            return redirect(url_for('job_status', job_id=job_id))

        # Extract Script ID
        import re
        info = job.stage_details.get('info', '')
        match = re.search(r"Script ID: ([\w-]+)", info)
        if not match:
            flash('Could not find script ID', 'error')
            return redirect(url_for('job_status', job_id=job_id))
            
        script_id = match.group(1)
        
        # Load Script with path traversal protection
        from src.utils.validation import validate_script_id, safe_path_join, PathTraversalError
        try:
            script_id = validate_script_id(script_id)
        except ValueError as e:
            flash(f'Invalid script ID: {e}', 'error')
            return redirect(url_for('job_status', job_id=job_id))
        
        try:
            scripts_dir = Path(__file__).parent.parent / 'output' / 'scripts'
            script_path = safe_path_join(scripts_dir, f"{script_id}.json")
        except PathTraversalError:
            flash('Invalid script path', 'error')
            return redirect(url_for('job_status', job_id=job_id))
        
        if not script_path.exists():
            flash('Script file not found', 'error')
            return redirect(url_for('job_status', job_id=job_id))
            
        import json
        with open(script_path, 'r') as f:
            script_data = json.load(f)

        profile = db.query(PodcastProfile).get(job.profile_id)
        return render_template('generate/review.html', job=job, profile=profile, script=script_data)
    finally:
        db.close()


@app.route('/jobs/<job_id>/approve', methods=['POST'])
def job_approve(job_id):
    """Approve script and resume generation."""
    db = get_db()
    try:
        job = db.query(GenerationJob).filter_by(job_id=job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        # 1. Parse JSON body (the edited script)
        script_data = request.json
        if script_data:
            # 2. Get Script ID
            import re
            info = job.stage_details.get('info', '')
            match = re.search(r"Script ID: ([\w-]+)", info)
            if match:
                 script_id = match.group(1)
                 script_path = Path(__file__).parent.parent / 'output' / 'scripts' / f"{script_id}.json"
                 
                 # 3. Read existing to preserve other fields (date, duration, etc)
                 import json
                 existing_data = {}
                 if script_path.exists():
                     with open(script_path, 'r') as f:
                         existing_data = json.load(f)
                 
                 # 4. Merge Updates
                 existing_data['episode_title'] = script_data.get('episode_title', existing_data.get('episode_title'))
                 existing_data['intro'] = script_data.get('intro', [])
                 existing_data['outro'] = script_data.get('outro', [])
                 
                 # Segments logic - ensure we map correctly
                 # The user might have renamed titles, but ids should be stable if we hid them
                 # We assume the array order is preserved
                 new_segments = []
                 incoming_segments = script_data.get('segments', [])
                 
                 for i, seg in enumerate(incoming_segments):
                      # Try to preserve duration estimate from original if possible
                      original_est = 60
                      try:
                          original_est = existing_data['segments'][i]['duration_estimate']
                      except (KeyError, IndexError, TypeError):
                         # Segment doesn't exist in original or has no duration_estimate
                         pass
                      
                      seg['duration_estimate'] = original_est
                      new_segments.append(seg)
                 
                 existing_data['segments'] = new_segments
                 
                 # 5. Save back to disk
                 with open(script_path, 'w') as f:
                     json.dump(existing_data, f, indent=2)
                 
        # 6. Resume
        gen_service.resume_generation_job(job_id)
        
        if request.accept_mimetypes.accept_json:
             return jsonify({'status': 'ok'})
             
        flash('Script approved! generating audio...', 'success')
        return redirect(url_for('job_status', job_id=job_id))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Error resuming job: {e}', 'error')
        return redirect(url_for('job_review', job_id=job_id))
    finally:
        db.close()


@app.route('/partials/jobs/<job_id>/status')
def job_status_partial(job_id):
    """View generation job status partial (for HTMX)."""
    db = get_db()
    try:
        job = db.query(GenerationJob).filter_by(job_id=job_id).first()
        if not job:
            return "Job not found", 404

        profile = db.query(PodcastProfile).get(job.profile_id)
        return render_template('generate/status_partial.html', job=job, profile=profile)
    finally:
        db.close()


@app.route('/jobs/<job_id>/cancel', methods=['POST'])
def job_cancel(job_id):
    """Cancel a running job."""
    if gen_service.cancel_job(job_id):
        flash('Job cancelled', 'success')
    else:
        flash('Could not cancel job (it may have already finished or failed)', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/jobs/<job_id>/retry', methods=['POST'])
def job_retry(job_id):
    """Retry a failed job with the same parameters."""
    db = get_db()
    try:
        # Get the original job
        original_job = db.query(GenerationJob).filter_by(job_id=job_id).first()
        if not original_job:
            flash('Original job not found', 'error')
            return redirect(url_for('jobs_list'))

        if original_job.status not in ['failed', 'cancelled']:
            flash('Can only retry failed or cancelled jobs', 'warning')
            return redirect(url_for('job_detail', job_id=job_id))

        # Extract options from stage_details if available
        stage_details = original_job.stage_details or {}
        options = {
            'duration': stage_details.get('duration', 15),
            'topic_count': stage_details.get('topic_count', 5),
            'tts_model': stage_details.get('tts_model', 'google'),
            'deep_research': stage_details.get('deep_research', True),
            'generate_audio': True,
            'generate_newsletter': True,
        }

        # Start a new job
        new_job_id = gen_service.start_generation_job(
            profile_id=original_job.profile_id,
            options=options
        )

        flash(f'Retry started! New job: {new_job_id[:12]}...', 'success')
        return redirect(url_for('job_status', job_id=new_job_id, profile_id=original_job.profile_id))

    except Exception as e:
        flash(f'Failed to retry: {str(e)[:100]}', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    finally:
        db.close()


# ============================================================
# ROUTES - RSS Feed
# ============================================================

@app.route('/profiles/<int:profile_id>/feed.xml')
def profile_feed(profile_id):
    """Generate RSS feed for a profile."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            return "Profile not found", 404

        episodes = db.query(Episode).filter_by(
            profile_id=profile_id,
            status='published'
        ).order_by(desc(Episode.date)).limit(50).all()

        return render_template('feed.xml',
            profile=profile,
            episodes=episodes,
            base_url=request.host_url.rstrip('/')
        ), {'Content-Type': 'application/xml'}
    finally:
        db.close()


# ============================================================
# API ROUTES (For Mobile App / External Consumers)
# ============================================================

@app.route('/api/profiles/<int:profile_id>/context')
def api_get_context(profile_id):
    """Get context for script generation."""
    db = get_db()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404

        week_ago = datetime.now() - timedelta(days=7)
        recent_topics = db.query(TopicHistory).join(Episode).filter(
            Episode.profile_id == profile_id,
            Episode.date >= week_ago
        ).all()

        avoided = db.query(TopicAvoidance).filter_by(
            profile_id=profile_id,
            is_active=True
        ).all()

        ongoing = db.query(TopicHistory).join(Episode).filter(
            Episode.profile_id == profile_id,
            TopicHistory.is_ongoing == True
        ).all()

        return jsonify({
            'profile': {
                'name': profile.name,
                'target_audience': profile.target_audience,
                'tone': profile.tone,
            },
            'recent_topics': [
                {
                    'title': t.title,
                    'category': t.category,
                    'key_points': t.key_points,
                    'date': t.created_at.isoformat() if t.created_at else None,
                }
                for t in recent_topics
            ],
            'topics_to_avoid': [
                {
                    'keyword': a.keyword,
                    'reason': a.reason,
                    'type': a.avoidance_type,
                }
                for a in avoided
            ],
            'ongoing_stories': [
                {
                    'title': o.title,
                    'follow_up_notes': o.follow_up_notes,
                }
                for o in ongoing
            ],
        })
    finally:
        db.close()


@app.route('/api/jobs/<job_id>/status')
@app.route('/api/jobs/<job_id>')
def api_job_status(job_id):
    """Get job status as JSON (for AJAX polling and mobile apps)."""
    status = gen_service.get_job_status(job_id)
    if not status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(status)


@app.route('/api/preview/<int:profile_id>')
def api_preview_content(profile_id):
    """Preview content that would be gathered for a profile."""
    # This would call the content ranker to get topics
    return jsonify({
        'message': 'Content preview not yet implemented',
        'topics': []
    })


# ============================================================
# AUDIO SERVING
# ============================================================

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve audio files with fallback path resolution."""
    base_output = Path(__file__).parent.parent / 'output'

    # Try multiple possible locations (episodes first - that's where mixed audio goes)
    possible_paths = [
        base_output / 'episodes' / filename,
        base_output / 'audio' / filename,
        base_output / filename,
        Path(filename),  # Absolute path fallback
    ]

    for path in possible_paths:
        if path.exists() and path.is_file():
            return send_file(path)

    # If still not found, try to extract just the filename and search
    just_filename = Path(filename).name
    for subdir in ['audio', 'episodes', '']:
        search_path = base_output / subdir / just_filename if subdir else base_output / just_filename
        if search_path.exists():
            return send_file(search_path)

    return jsonify({'error': f'Audio file not found: {filename}'}), 404


# ============================================================
# SETTINGS
# ============================================================

@app.route('/settings')
def settings_page():
    """Application settings page."""
    db = get_db()
    try:
        # Get or create app settings
        settings = db.query(AppSettings).first()
        if not settings:
            settings = AppSettings(key='global_settings')
            db.add(settings)
            db.commit()
        return render_template('settings.html', settings=settings)
    finally:
        db.close()


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update application settings."""
    db = get_db()
    try:
        settings = db.query(AppSettings).first()
        if not settings:
            settings = AppSettings(key='global_settings')
            db.add(settings)
            db.commit()

        if request.method == 'POST':
            data = request.json

            # Update settings from request data
            if 'theme' in data:
                settings.theme = data['theme']
            if 'language' in data:
                settings.language = data['language']
            if 'auto_save' in data:
                settings.auto_save = data['auto_save']
            if 'default_duration' in data:
                settings.default_duration = int(data['default_duration'])
            if 'default_topics' in data:
                settings.default_topics = int(data['default_topics'])
            if 'research_depth' in data:
                settings.research_depth = data['research_depth']
            if 'ai_model' in data:
                settings.ai_model = data['ai_model']
            if 'audio_quality' in data:
                settings.audio_quality = data['audio_quality']
            if 'tts_provider' in data:
                settings.tts_provider = data['tts_provider']
            if 'playback_speed' in data:
                settings.playback_speed = float(data['playback_speed'])
            if 'enable_notifications' in data:
                settings.enable_notifications = data['enable_notifications']
            if 'email_notifications' in data:
                settings.email_notifications = data['email_notifications']

            db.commit()
            return jsonify({'success': True, 'message': 'Settings saved'})

        # GET request - return current settings
        return jsonify({
            'theme': settings.theme or 'system',
            'language': settings.language or 'en',
            'auto_save': settings.auto_save if hasattr(settings, 'auto_save') else True,
            'default_duration': settings.default_duration or 15,
            'default_topics': settings.default_topics or 3,
            'research_depth': settings.research_depth or 'standard',
            'ai_model': settings.ai_model or 'gemini-pro',
            'audio_quality': settings.audio_quality or 'high',
            'tts_provider': settings.tts_provider or 'google',
            'playback_speed': settings.playback_speed or 1.0,
            'enable_notifications': settings.enable_notifications if hasattr(settings, 'enable_notifications') else True,
            'email_notifications': settings.email_notifications if hasattr(settings, 'email_notifications') else False
        })
    finally:
        db.close()


@app.route('/api/settings/api-keys', methods=['POST'])
def save_api_key():
    """Save API key securely."""
    data = request.json
    key_name = data.get('key_name')
    key_value = data.get('key_value')

    if not key_name or not key_value:
        return jsonify({'error': 'Missing key name or value'}), 400

    # Map key names to environment variables
    key_mapping = {
        'gemini': 'GEMINI_API_KEY',
        'elevenlabs': 'ELEVENLABS_API_KEY',
        'openai': 'OPENAI_API_KEY'
    }

    env_var = key_mapping.get(key_name)
    if not env_var:
        return jsonify({'error': 'Unknown API key type'}), 400

    # Save to environment (for current session)
    os.environ[env_var] = key_value

    # Optionally save to .env file
    env_file = Path(__file__).parent.parent / '.env'
    try:
        # Read existing .env content
        existing = {}
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        existing[k] = v

        # Update with new key
        existing[env_var] = key_value

        # Write back
        with open(env_file, 'w') as f:
            for k, v in existing.items():
                f.write(f'{k}={v}\n')

        return jsonify({'success': True, 'message': f'{key_name.upper()} API key saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/validate-keys', methods=['GET'])
def validate_api_keys():
    """Validate all configured API keys."""
    results = {}

    # Check Gemini API Key
    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content("Say 'OK' if you can hear me.")
            results['gemini'] = {
                'configured': True,
                'valid': True,
                'message': 'Gemini API key is valid'
            }
        except Exception as e:
            results['gemini'] = {
                'configured': True,
                'valid': False,
                'message': f'Invalid: {str(e)[:100]}'
            }
    else:
        results['gemini'] = {
            'configured': False,
            'valid': False,
            'message': 'Not configured'
        }

    # Check Google TTS API Key
    google_tts_key = os.getenv('GOOGLE_TTS_API_KEY')
    if google_tts_key:
        try:
            from google.cloud import texttospeech
            # Just check if the key exists - full validation would require project setup
            results['google_tts'] = {
                'configured': True,
                'valid': True,
                'message': 'Google TTS API key configured (not fully validated)'
            }
        except Exception as e:
            results['google_tts'] = {
                'configured': True,
                'valid': False,
                'message': f'Error: {str(e)[:100]}'
            }
    else:
        results['google_tts'] = {
            'configured': False,
            'valid': False,
            'message': 'Not configured (optional)'
        }

    # Check ElevenLabs API Key
    elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
    if elevenlabs_key:
        try:
            import requests
            resp = requests.get(
                'https://api.elevenlabs.io/v1/user',
                headers={'xi-api-key': elevenlabs_key},
                timeout=10
            )
            if resp.status_code == 200:
                results['elevenlabs'] = {
                    'configured': True,
                    'valid': True,
                    'message': 'ElevenLabs API key is valid'
                }
            else:
                results['elevenlabs'] = {
                    'configured': True,
                    'valid': False,
                    'message': f'Invalid: HTTP {resp.status_code}'
                }
        except Exception as e:
            results['elevenlabs'] = {
                'configured': True,
                'valid': False,
                'message': f'Error: {str(e)[:100]}'
            }
    else:
        results['elevenlabs'] = {
            'configured': False,
            'valid': False,
            'message': 'Not configured (optional)'
        }

    # Overall status
    required_valid = results.get('gemini', {}).get('valid', False)
    all_configured = all(r.get('configured', False) for r in results.values())

    return jsonify({
        'keys': results,
        'ready': required_valid,
        'message': 'Ready for generation!' if required_valid else 'Missing required API keys'
    })


@app.route('/api/settings/storage')
def storage_info():
    """Get storage usage information."""
    output_dir = Path(__file__).parent.parent / 'output'
    cache_dir = Path(__file__).parent.parent / '.cache'

    def get_dir_size(path):
        total = 0
        if path.exists():
            for f in path.rglob('*'):
                if f.is_file():
                    total += f.stat().st_size
        return total

    db = get_db()
    try:
        episode_count = db.query(Episode).count()
        audio_size = get_dir_size(output_dir)
        cache_size = get_dir_size(cache_dir)

        return jsonify({
            'episodes': episode_count,
            'audio_size': audio_size,
            'audio_size_formatted': f'{audio_size / (1024*1024):.1f} MB',
            'cache_size': cache_size,
            'cache_size_formatted': f'{cache_size / (1024*1024):.1f} MB',
            'total_size': audio_size + cache_size,
            'total_size_formatted': f'{(audio_size + cache_size) / (1024*1024):.1f} MB'
        })
    finally:
        db.close()


@app.route('/api/settings/clear-cache', methods=['POST'])
def clear_cache():
    """Clear application cache."""
    cache_dir = Path(__file__).parent.parent / '.cache'
    try:
        import shutil
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(exist_ok=True)
        return jsonify({'success': True, 'message': 'Cache cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# AI SUGGESTION APIs
# ============================================================

@app.route('/api/ai-suggest', methods=['POST'])
def ai_suggest():
    """Get AI suggestions for podcast idea refinement."""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')

        # Use Gemini to generate suggestions
        import google.generativeai as genai

        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'suggestion': 'AI suggestions require GEMINI_API_KEY to be configured.'})

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        response = model.generate_content(prompt)
        suggestion = response.text if response.text else 'Unable to generate suggestion.'

        return jsonify({'suggestion': suggestion})
    except Exception as e:
        return jsonify({'suggestion': f'AI suggestion unavailable: {str(e)[:100]}'}), 200


@app.route('/api/suggest-sources', methods=['POST'])
def suggest_sources():
    """Suggest content sources based on podcast idea."""
    try:
        data = request.get_json()
        idea = data.get('idea', '')
        audience = data.get('audience', '')

        # Default sources based on common categories
        default_sources = [
            {'id': 'reddit_tech', 'name': 'Reddit - Tech', 'description': 'r/technology, r/programming for tech news'},
            {'id': 'reddit_news', 'name': 'Reddit - News', 'description': 'r/news, r/worldnews for current events'},
            {'id': 'google_news', 'name': 'Google News', 'description': 'Aggregated news from multiple sources'},
            {'id': 'rss_tech', 'name': 'Tech RSS Feeds', 'description': 'TechCrunch, Ars Technica, The Verge'},
        ]

        # Try to get AI-powered suggestions
        try:
            import google.generativeai as genai
            api_key = os.getenv('GEMINI_API_KEY')

            if api_key and idea:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash')

                prompt = f"""Based on this podcast idea: "{idea}" and target audience: "{audience or 'general'}",
                suggest 4-6 content sources. For each, provide: id (lowercase, no spaces), name, and brief description.
                Format as JSON array: [{{"id": "...", "name": "...", "description": "..."}}]
                Focus on Reddit subreddits, RSS feeds, and Google News queries relevant to the topic."""

                response = model.generate_content(prompt)
                if response.text:
                    import json
                    # Try to extract JSON from response
                    text = response.text
                    if '```json' in text:
                        text = text.split('```json')[1].split('```')[0]
                    elif '```' in text:
                        text = text.split('```')[1].split('```')[0]
                    sources = json.loads(text.strip())
                    return jsonify({
                        'sources': sources,
                        'explanation': f'AI-recommended sources for your podcast about {idea[:50]}...'
                    })
        except Exception as e:
            pass  # Fall back to defaults

        return jsonify({
            'sources': default_sources,
            'explanation': 'Recommended sources to get you started:'
        })
    except Exception as e:
        return jsonify({
            'sources': [],
            'explanation': f'Error: {str(e)}'
        }), 200


# ============================================================
# SCHEDULER STATUS
# ============================================================

@app.route('/api/scheduler/status')
def scheduler_status():
    """Get scheduler status and scheduled jobs."""
    try:
        from webapp.scheduler import get_scheduled_jobs, get_scheduler
        sched = get_scheduler()
        return jsonify({
            'running': sched.running if sched else False,
            'jobs': get_scheduled_jobs()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors with custom page."""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with custom page."""
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()
    try:
        db.rollback()
    except Exception as rollback_error:
        # Log rollback failure but don't mask the original error
        logger.warning(f"Database rollback failed during 500 error handling: {rollback_error}")
    finally:
        db.close()

    # Log the original error
    logger.error(f"Internal server error: {error}")
    return render_template('errors/500.html'), 500


@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 forbidden errors."""
    flash('Access denied', 'error')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    # Ensure templates directory exists
    template_dir = Path(__file__).parent / 'templates'
    if not template_dir.exists():
        print(f"Warning: Template directory {template_dir} does not exist!")

    # Initialize the scheduler
    try:
        from webapp.scheduler import init_scheduler
        scheduler = init_scheduler()
        print("Scheduler initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize scheduler: {e}")

    print("\n" + "="*60)
    print("PODCAST STUDIO v2")
    print("="*60)
    print("Open http://127.0.0.1:8000 in your browser (Unified Application)")
    print("="*60 + "\n")

    app.run(debug=True, port=8000, use_reloader=False)
