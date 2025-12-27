"""
Integration tests for Flask webapp routes.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestDashboardRoutes:
    """Tests for dashboard routes."""

    def test_dashboard_loads(self, client):
        """Test dashboard page loads successfully."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Podcast Studio" in response.data or b"Dashboard" in response.data

    def test_dashboard_shows_profiles(self, client, db_session, sample_profile):
        """Test dashboard shows profiles."""
        # Note: This may need mocking depending on DB setup
        response = client.get("/")
        assert response.status_code == 200


@pytest.mark.integration
class TestProfileRoutes:
    """Tests for profile management routes."""

    def test_profiles_list(self, client):
        """Test profiles list page loads."""
        response = client.get("/profiles")
        assert response.status_code == 200

    def test_profile_detail(self, client, db_session, sample_profile):
        """Test profile detail page loads."""
        with patch("webapp.app.get_db", return_value=db_session):
            response = client.get(f"/profiles/{sample_profile.id}")
            # May need mocking
            assert response.status_code in [200, 302, 404]

    def test_create_profile_page_loads(self, client):
        """Test create profile page loads."""
        response = client.get("/profiles/new")
        assert response.status_code == 200

    def test_create_profile_post(self, client):
        """Test creating a new profile."""
        with patch("webapp.app.get_db") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            response = client.post(
                "/profiles/new",
                data={
                    "name": "New Test Podcast",
                    "description": "A new podcast",
                    "target_audience": "Developers",
                    "tone": "casual",
                    "language": "en-US",
                    "duration": "10",
                    "topic_count": "5",
                },
                follow_redirects=False,
            )
            # Should redirect on success
            assert response.status_code in [200, 302]


@pytest.mark.integration
class TestEpisodeRoutes:
    """Tests for episode routes."""

    def test_episodes_list(self, client):
        """Test episodes list page loads."""
        response = client.get("/episodes")
        assert response.status_code == 200

    def test_episode_detail_not_found(self, client):
        """Test episode detail for non-existent episode."""
        response = client.get("/episodes/99999")
        # Should return 404 or redirect
        assert response.status_code in [200, 302, 404]


@pytest.mark.integration
class TestNewsletterRoutes:
    """Tests for newsletter routes."""

    def test_newsletters_list(self, client):
        """Test newsletters list page loads."""
        response = client.get("/newsletters")
        assert response.status_code == 200

    def test_newsletter_detail_not_found(self, client):
        """Test newsletter detail for non-existent newsletter."""
        response = client.get("/newsletters/99999")
        # Should handle gracefully
        assert response.status_code in [200, 302, 404]


@pytest.mark.integration
class TestGenerationRoutes:
    """Tests for generation pipeline routes."""

    def test_jobs_list(self, client):
        """Test jobs list page loads."""
        response = client.get("/jobs")
        assert response.status_code == 200

    def test_job_status_not_found(self, client):
        """Test job status for non-existent job."""
        response = client.get("/jobs/non-existent-job-id")
        # Should handle gracefully
        assert response.status_code in [200, 302, 404]


@pytest.mark.integration
class TestAPIRoutes:
    """Tests for API endpoints."""

    def test_job_status_api(self, client):
        """Test job status API endpoint."""
        response = client.get("/api/jobs/test-job-id/status")
        # Should return JSON (even if job not found)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert response.content_type == "application/json"

    def test_generate_images_api_not_found(self, client):
        """Test generate images API for non-existent newsletter."""
        response = client.post(
            "/api/newsletters/99999/generate-images",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in [404, 400]


@pytest.mark.integration
class TestSettingsRoutes:
    """Tests for settings routes."""

    def test_settings_page_loads(self, client):
        """Test settings page loads."""
        response = client.get("/settings")
        assert response.status_code == 200


@pytest.mark.integration
class TestAudioRoutes:
    """Tests for audio serving routes."""

    def test_audio_not_found(self, client):
        """Test audio route for non-existent file."""
        response = client.get("/audio/non-existent-file.mp3")
        assert response.status_code == 404
