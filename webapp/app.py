"""
Podcast Production Studio - Web Application v2
A comprehensive webapp for managing podcast generation workflows.
"""

import os
import sys
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from sqlalchemy import desc
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp.models import (
    Base, PodcastProfile, Host, Episode, TopicHistory,
    TopicAvoidance, ContentSource, GenerationJob, AppSettings,
    init_db
)
from webapp.services.generation_service import GenerationService

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'podcast-studio-dev-key-v2')

# Database setup
DB_PATH = Path(__file__).parent / 'podcast_studio.db'
engine = init_db(str(DB_PATH))
Session = sessionmaker(bind=engine)

# Initialize Services
# We pass the Session factory, not an instance, so the service can manage its own threads/scopes
gen_service = GenerationService(Session)


def get_db():
    """Get database session."""
    return Session()


# ============================================================
# ROUTES - Dashboard
# ============================================================

@app.route('/')
def dashboard():
    """Main dashboard showing all profiles and recent activity."""
    db = get_db()
    try:
        profiles = db.query(PodcastProfile).filter_by(is_active=True).all()
        recent_episodes = db.query(Episode).order_by(desc(Episode.created_at)).limit(10).all()
        running_jobs_db = db.query(GenerationJob).filter(
            GenerationJob.status.in_(['running', 'pending'])
        ).all()

        return render_template('dashboard.html',
            profiles=profiles,
            recent_episodes=recent_episodes,
            running_jobs=running_jobs_db
        )
    finally:
        db.close()


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
            # Parse categories from form
            categories = request.form.getlist('categories')

            profile = PodcastProfile(
                name=request.form['name'],
                description=request.form.get('description', ''),
                target_audience=request.form.get('target_audience', ''),
                tone=request.form.get('tone', 'conversational'),
                language=request.form.get('language', 'en-US'),
                target_duration_minutes=int(request.form.get('duration', 10)),
                topic_count=int(request.form.get('topic_count', 5)),
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
        profile = db.query(PodcastProfile).get(profile_id)
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
            profile.name = request.form['name']
            profile.description = request.form.get('description', '')
            profile.target_audience = request.form.get('target_audience', '')
            profile.tone = request.form.get('tone', 'conversational')
            profile.language = request.form.get('language', 'en-US')
            profile.target_duration_minutes = int(request.form.get('duration', 10))
            profile.topic_count = int(request.form.get('topic_count', 5))
            profile.categories = request.form.getlist('categories')

            # Handle scheduling fields
            schedule_was_enabled = profile.schedule_enabled
            profile.schedule_enabled = 'schedule_enabled' in request.form
            profile.schedule_hour = int(request.form.get('schedule_hour', 6))
            profile.schedule_minute = int(request.form.get('schedule_minute', 0))
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
            expertise = [x.strip() for x in request.form.get('expertise_areas', '').split(',') if x.strip()]
            host = Host(
                profile_id=profile_id,
                name=request.form['name'],
                persona=request.form.get('persona', ''),
                voice_name=request.form.get('voice_name', 'Puck'),
                speaking_style=request.form.get('speaking_style', ''),
                expertise_areas=expertise,
            )
            db.add(host)
            db.commit()
            flash(f'Host "{host.name}" added!', 'success')
            return redirect(url_for('profile_detail', profile_id=profile_id))

        # Available voices
        voices = ['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede', 'Leda', 'Orus', 'Zephyr',
                  'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba']

        return render_template('hosts/new.html', profile=profile, voices=voices)
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

        voices = ['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede', 'Leda', 'Orus', 'Zephyr',
                  'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba']

        return render_template('hosts/edit.html', profile=profile, host=host, voices=voices)
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
            config = {}
            source_type = request.form['source_type']

            if source_type == 'reddit':
                config['subreddit'] = request.form.get('subreddit', '')
            elif source_type == 'rss':
                config['url'] = request.form.get('rss_url', '')
            elif source_type == 'google_news':
                config['query'] = request.form.get('search_query', '')

            source = ContentSource(
                profile_id=profile_id,
                name=request.form['name'],
                source_type=source_type,
                config=config,
                priority=int(request.form.get('priority', 5)),
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

        episodes = db.query(Episode).order_by(desc(Episode.date)).limit(per_page).offset((page-1)*per_page).all()
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
            topics=topics
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
def generate_episode(profile_id):
    """Start podcast generation."""
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
        
        # Load Script
        # We need a way to get the path. 
        # Using a hack: Construct path knowing the structure
        script_path = Path(__file__).parent.parent / 'output' / 'scripts' / f"{script_id}.json"
        
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
                      except: pass
                      
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
def api_job_status(job_id):
    """Get job status as JSON (for mobile apps or manual polling)."""
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
    """Serve audio files."""
    audio_dir = Path(__file__).parent.parent / 'output' / 'audio'
    return send_file(audio_dir / filename)


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
    print("Open http://127.0.0.1:5050 in your browser")
    print("="*60 + "\n")

    app.run(debug=True, port=5050, use_reloader=False)
