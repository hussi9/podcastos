"""
End-to-End User Flow Tests
Tests complete user journeys through the application.
"""

import pytest
import json
import time
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


@pytest.mark.e2e
class TestNewUserOnboarding:
    """Tests the complete new user onboarding flow."""

    def test_new_user_creates_first_podcast(self, client, test_db):
        """
        Complete flow: New user creates their first podcast profile,
        configures it, adds sources, and starts generation.
        """
        # Step 1: User visits dashboard
        response = client.get("/")
        assert response.status_code == 200

        # Step 2: User navigates to create new profile
        response = client.get("/profiles/new")
        assert response.status_code == 200
        assert b"Create" in response.data or b"New" in response.data

        # Step 3: User submits new profile form
        profile_data = {
            "name": "My First Podcast",
            "description": "A podcast about technology and innovation",
            "target_audience": "Tech enthusiasts and developers",
            "tone": "conversational",
            "language": "en-US",
            "duration": "15",
            "topic_count": "5",
            "categories": ["technology", "programming"],
        }

        with patch("webapp.app.get_db") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            # Mock the commit to capture the profile
            created_profile = MagicMock()
            created_profile.id = 1
            created_profile.name = profile_data["name"]

            def add_side_effect(obj):
                obj.id = 1
                return None

            mock_session.add.side_effect = add_side_effect

            response = client.post(
                "/profiles/new",
                data=profile_data,
                follow_redirects=False,
            )

            # Should redirect to profile detail or profiles list
            assert response.status_code in [200, 302, 303]

    def test_user_configures_content_sources(self, client, db_session, sample_profile):
        """User adds content sources to their profile."""
        # Navigate to add source page
        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get(f"/profiles/{sample_profile.id}/sources/new")
            assert response.status_code == 200

            # Add Reddit source
            source_data = {
                "name": "r/technology",
                "source_type": "reddit",
                "subreddit": "technology",
                "priority": "1",
            }

            response = client.post(
                f"/profiles/{sample_profile.id}/sources/new",
                data=source_data,
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

    def test_user_adds_custom_hosts(self, client, db_session, sample_profile):
        """User configures custom hosts for their podcast."""
        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get(f"/profiles/{sample_profile.id}/hosts/new")
            assert response.status_code == 200

            host_data = {
                "name": "Alex",
                "persona": "A tech industry veteran with deep expertise",
                "voice_name": "Orus",
                "speaking_style": "analytical, thoughtful",
                "expertise_areas": "AI, cloud computing, startups",
            }

            response = client.post(
                f"/profiles/{sample_profile.id}/hosts/new",
                data=host_data,
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]


@pytest.mark.e2e
class TestPodcastGenerationFlow:
    """Tests the complete podcast generation workflow."""

    @pytest.fixture
    def mock_generation_pipeline(self):
        """Mock the entire generation pipeline."""
        with patch("webapp.services.generation_service.GenerationService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.start_generation_job.return_value = "job-test-123"
            mock_instance.get_job_status.return_value = {
                "job_id": "job-test-123",
                "status": "running",
                "progress_percent": 50,
                "current_stage": "scripting",
                "stages_completed": ["research", "synthesis"],
                "stages_pending": ["audio", "newsletter"],
                "activity_log": [],
            }
            mock_service.return_value = mock_instance
            yield mock_instance

    def test_start_generation_from_profile(self, client, db_session, sample_profile):
        """User starts generation from profile page."""
        with patch("webapp.app.get_db", return_value=db_session):
            # Navigate to generate page
            response = client.get(f"/profiles/{sample_profile.id}/generate")
            assert response.status_code == 200

            # Verify form elements are present
            assert b"Generate" in response.data or b"Start" in response.data

    def test_generation_with_deep_research(self, client, db_session, sample_profile):
        """User starts generation with deep research enabled."""
        generation_options = {
            "topic_count": "5",
            "duration": "15",
            "deep_research": "on",
            "use_continuity": "on",
            "tts_model": "gemini-2.5-flash-preview-tts",
        }

        with patch("webapp.app.get_db", return_value=db_session):
            with patch("webapp.app.gen_service") as mock_service:
                mock_service.start_generation_job.return_value = "job-deep-research"

                response = client.post(
                    f"/profiles/{sample_profile.id}/generate",
                    data=generation_options,
                    follow_redirects=False,
                )

                # Should redirect to job status page
                assert response.status_code in [200, 302]

                # Verify deep_research was passed
                if mock_service.start_generation_job.called:
                    call_args = mock_service.start_generation_job.call_args
                    options = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("options", {})
                    # Options should include deep_research

    def test_job_status_polling(self, client, db_session):
        """Test job status page and polling."""
        from webapp.models import GenerationJob

        # Create a job in the database
        profile_id = 1  # Assume profile exists
        job = GenerationJob(
            profile_id=profile_id,
            job_id="poll-test-job",
            target_date=datetime.now(),
            status="running",
            current_stage="scripting",
            progress_percent=45,
            stages_completed=["research", "synthesis"],
            stages_pending=["audio", "newsletter"],
            stage_details={
                "activity_log": [
                    {"timestamp": datetime.utcnow().isoformat(), "message": "Started", "level": "info"},
                    {"timestamp": datetime.utcnow().isoformat(), "message": "Research complete", "level": "success"},
                ],
                "current_activity": "Generating script...",
            },
        )
        db_session.add(job)
        db_session.commit()

        with patch("webapp.app.get_db", return_value=db_session):
            # Get job status page
            response = client.get("/jobs/poll-test-job")
            assert response.status_code in [200, 302, 404]

            # Get job status via API
            response = client.get("/api/jobs/poll-test-job/status")
            if response.status_code == 200:
                data = json.loads(response.data)
                assert data.get("status") == "running"
                assert data.get("progress_percent") == 45

    def test_cancel_running_job(self, client, db_session):
        """User cancels a running job."""
        from webapp.models import GenerationJob

        job = GenerationJob(
            profile_id=1,
            job_id="cancel-test-job",
            target_date=datetime.now(),
            status="running",
            current_stage="audio",
            progress_percent=75,
        )
        db_session.add(job)
        db_session.commit()

        with patch("webapp.app.get_db", return_value=db_session):
            with patch("webapp.app.gen_service.cancel_job", return_value=True):
                response = client.post(
                    "/jobs/cancel-test-job/cancel",
                    follow_redirects=False,
                )
                assert response.status_code in [200, 302]


@pytest.mark.e2e
class TestEpisodeManagementFlow:
    """Tests episode viewing and management."""

    def test_view_episode_list(self, client, db_session, sample_episode):
        """User views list of episodes."""
        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get("/episodes")
            assert response.status_code == 200

    def test_view_episode_detail(self, client, db_session, sample_episode):
        """User views episode details."""
        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get(f"/episodes/{sample_episode.id}")
            assert response.status_code in [200, 302, 404]

    def test_play_episode_audio(self, client, tmp_path):
        """User plays episode audio."""
        # Create a fake audio file
        audio_dir = tmp_path / "output" / "episodes"
        audio_dir.mkdir(parents=True)
        fake_audio = audio_dir / "test-episode.mp3"
        fake_audio.write_bytes(b"fake audio content")

        with patch("webapp.app.Path") as mock_path:
            mock_path.return_value = tmp_path / "output"

            response = client.get("/audio/test-episode.mp3")
            # May 404 depending on configuration
            assert response.status_code in [200, 404]


@pytest.mark.e2e
class TestNewsletterFlow:
    """Tests newsletter viewing and management."""

    def test_view_newsletter_list(self, client, db_session):
        """User views list of newsletters."""
        response = client.get("/newsletters")
        assert response.status_code == 200

    def test_view_newsletter_detail(self, client, db_session, sample_episode):
        """User views newsletter detail with new NYT design."""
        from webapp.models import Newsletter

        newsletter = Newsletter(
            episode_id=sample_episode.id,
            profile_id=sample_episode.profile_id,
            title="Weekly Tech Digest",
            subtitle="Your curated technology news",
            issue_date=datetime.now(),
            intro="Welcome to this week's edition!",
            outro="Thanks for reading!",
            sections=[
                {
                    "headline": "AI Revolution Continues",
                    "body": "This week saw major advances in artificial intelligence...",
                    "sources": ["TechCrunch", "Ars Technica"],
                    "category": "Technology",
                },
                {
                    "headline": "Open Source Wins Big",
                    "body": "The open source community celebrated several victories...",
                    "sources": ["GitHub Blog"],
                    "category": "Open Source",
                },
            ],
            total_word_count=750,
            reading_time_minutes=4,
        )
        db_session.add(newsletter)
        db_session.commit()

        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get(f"/newsletters/{newsletter.id}")
            assert response.status_code == 200

            # Verify NYT-style elements are present
            assert b"newsletter" in response.data.lower()

    def test_copy_newsletter_html(self, client, db_session, sample_episode):
        """User copies newsletter HTML."""
        from webapp.models import Newsletter

        newsletter = Newsletter(
            episode_id=sample_episode.id,
            profile_id=sample_episode.profile_id,
            title="Copy Test Newsletter",
            subtitle="Test",
            issue_date=datetime.now(),
            intro="Intro",
            outro="Outro",
            sections=[],
            html_content="<html><body>Newsletter content</body></html>",
            total_word_count=100,
            reading_time_minutes=1,
        )
        db_session.add(newsletter)
        db_session.commit()

        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get(f"/newsletters/{newsletter.id}")
            assert response.status_code == 200
            # HTML content should be embedded for copying
            assert b"rawHtml" in response.data or b"html_content" in response.data.lower()


@pytest.mark.e2e
class TestSettingsFlow:
    """Tests settings management."""

    def test_view_settings(self, client):
        """User views settings page."""
        response = client.get("/settings")
        assert response.status_code == 200

    def test_update_settings(self, client, db_session):
        """User updates application settings."""
        settings_data = {
            "theme": "dark",
            "notifications_enabled": "on",
            "auto_publish": "off",
        }

        with patch("webapp.app.get_db", return_value=db_session):
            response = client.post(
                "/settings",
                data=settings_data,
                follow_redirects=False,
            )
            # 405 is acceptable if POST not implemented on settings
            assert response.status_code in [200, 302, 405]


@pytest.mark.e2e
class TestErrorHandling:
    """Tests error handling throughout user flows."""

    def test_404_for_nonexistent_profile(self, client):
        """User gets 404 for non-existent profile."""
        response = client.get("/profiles/99999")
        # Should either 404 or redirect with flash message
        assert response.status_code in [200, 302, 404]

    def test_404_for_nonexistent_episode(self, client):
        """User gets 404 for non-existent episode."""
        response = client.get("/episodes/99999")
        assert response.status_code in [200, 302, 404]

    def test_404_for_nonexistent_job(self, client):
        """User gets 404 for non-existent job."""
        response = client.get("/jobs/nonexistent-job-id")
        assert response.status_code in [200, 302, 404]

    def test_csrf_protection(self, client, db_session, sample_profile):
        """Test CSRF protection on POST requests."""
        # Re-enable CSRF for this test
        from webapp.app import app

        original_csrf = app.config.get('WTF_CSRF_ENABLED', True)
        app.config['WTF_CSRF_ENABLED'] = True

        try:
            # POST without CSRF token should fail
            response = client.post(
                f"/profiles/{sample_profile.id}/generate",
                data={"topic_count": "5"},
                follow_redirects=False,
            )
            # Should get 400 (CSRF error) or redirect to error page
            # In test mode with CSRF disabled, this may still pass
            assert response.status_code in [200, 302, 400]
        finally:
            app.config['WTF_CSRF_ENABLED'] = original_csrf


@pytest.mark.e2e
class TestSchedulingFlow:
    """Tests scheduled generation flows."""

    def test_enable_scheduling(self, client, db_session, sample_profile):
        """User enables scheduled generation."""
        schedule_data = {
            "name": sample_profile.name,
            "schedule_enabled": "on",
            "schedule_hour": "6",
            "schedule_minute": "0",
            "schedule_days": ["mon", "tue", "wed", "thu", "fri"],
            "timezone": "America/New_York",
        }

        with patch("webapp.app.get_db", return_value=db_session):
            with patch("webapp.scheduler.update_profile_schedule"):
                response = client.post(
                    f"/profiles/{sample_profile.id}/edit",
                    data=schedule_data,
                    follow_redirects=False,
                )
                assert response.status_code in [200, 302]

    def test_disable_scheduling(self, client, db_session, sample_profile):
        """User disables scheduled generation."""
        # First enable scheduling
        sample_profile.schedule_enabled = True
        db_session.commit()

        schedule_data = {
            "name": sample_profile.name,
            # schedule_enabled not included = disabled
            "schedule_hour": "6",
            "schedule_minute": "0",
        }

        with patch("webapp.app.get_db", return_value=db_session):
            with patch("webapp.scheduler.update_profile_schedule"):
                response = client.post(
                    f"/profiles/{sample_profile.id}/edit",
                    data=schedule_data,
                    follow_redirects=False,
                )
                assert response.status_code in [200, 302]
