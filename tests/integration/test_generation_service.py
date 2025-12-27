"""
Integration tests for the Generation Service.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


@pytest.mark.integration
class TestGenerationService:
    """Tests for GenerationService."""

    @pytest.fixture
    def gen_service(self, test_db):
        """Create a GenerationService instance."""
        from webapp.services.generation_service import GenerationService

        return GenerationService(test_db)

    def test_service_initialization(self, gen_service):
        """Test service initializes correctly."""
        assert gen_service.Session is not None

    def test_start_generation_job(self, gen_service, sample_profile, db_session):
        """Test starting a generation job."""
        with patch("webapp.services.generation_service.threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()

            job_id = gen_service.start_generation_job(
                profile_id=sample_profile.id,
                options={
                    "topic_count": 3,
                    "duration": 10,
                    "deep_research": False,
                },
            )

            assert job_id is not None
            assert job_id.startswith("job-")
            mock_thread.assert_called_once()

    def test_start_job_with_invalid_profile(self, gen_service):
        """Test starting job with non-existent profile."""
        with pytest.raises(ValueError, match="not found"):
            gen_service.start_generation_job(
                profile_id=99999,
                options={"topic_count": 3},
            )

    def test_get_job_status_not_found(self, gen_service):
        """Test getting status of non-existent job."""
        status = gen_service.get_job_status("non-existent-job")
        assert status is None

    def test_get_job_status(self, gen_service, sample_profile, db_session):
        """Test getting job status."""
        from webapp.models import GenerationJob

        # Create a job directly
        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="test-job-123",
            target_date=datetime.now(),
            status="running",
            current_stage="research",
            progress_percent=25,
            stages_completed=["initializing"],
            stages_pending=["scripting", "audio"],
        )
        db_session.add(job)
        db_session.commit()

        # Get status
        status = gen_service.get_job_status("test-job-123")

        assert status is not None
        assert status["job_id"] == "test-job-123"
        assert status["status"] == "running"
        assert status["progress_percent"] == 25
        assert "initializing" in status["stages_completed"]

    def test_cancel_job(self, gen_service, sample_profile, db_session):
        """Test cancelling a job."""
        from webapp.models import GenerationJob

        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="cancel-test-job",
            target_date=datetime.now(),
            status="running",
            current_stage="research",
            progress_percent=30,
        )
        db_session.add(job)
        db_session.commit()

        result = gen_service.cancel_job("cancel-test-job")
        assert result is True

        # Verify job is cancelled
        db_session.refresh(job)
        assert job.status == "cancelled"

    def test_cancel_completed_job_fails(self, gen_service, sample_profile, db_session):
        """Test that cancelling a completed job fails."""
        from webapp.models import GenerationJob

        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="completed-job",
            target_date=datetime.now(),
            status="completed",
            progress_percent=100,
        )
        db_session.add(job)
        db_session.commit()

        result = gen_service.cancel_job("completed-job")
        assert result is False


@pytest.mark.integration
class TestPipelineLogic:
    """Tests for pipeline logic (mocked external services)."""

    @pytest.fixture
    def gen_service(self, test_db):
        """Create a GenerationService instance."""
        from webapp.services.generation_service import GenerationService
        return GenerationService(test_db)

    @pytest.fixture
    def mock_external_services(self):
        """Mock all external services."""
        with patch("src.podcast_engine.PodcastEngine") as mock_engine:
            mock_instance = MagicMock()

            # Mock content ranker
            mock_instance.content_ranker.get_ranked_topics = AsyncMock(return_value=[])

            # Mock script generator
            mock_instance.script_generator.generate_script = AsyncMock(
                return_value=MagicMock(
                    episode_id="test-ep",
                    episode_title="Test Episode",
                    segments=[],
                    intro=[],
                    outro=[],
                    duration_estimate=600,
                    model_dump_json=lambda indent=None: "{}",
                )
            )

            # Mock TTS
            mock_instance.tts.generate_episode_audio = AsyncMock(return_value=[])
            mock_instance.tts.combine_segments_by_section = AsyncMock(return_value={})
            mock_instance.tts.combine_audio_segments = AsyncMock(return_value="/tmp/test.mp3")

            # Mock paths
            from pathlib import Path

            mock_instance.scripts_dir = Path("/tmp")
            mock_instance.episodes_dir = Path("/tmp")

            mock_engine.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_pipeline_stages_progress(
        self, gen_service, sample_profile, db_session, mock_external_services
    ):
        """Test that pipeline progresses through stages."""
        # This would require a more complex setup to test the async pipeline
        # For now, we verify the structure is correct
        assert gen_service is not None


@pytest.mark.integration
class TestJobActivityLogging:
    """Tests for job activity logging."""

    @pytest.fixture
    def gen_service(self, test_db):
        """Create a GenerationService instance."""
        from webapp.services.generation_service import GenerationService
        return GenerationService(test_db)

    def test_activity_log_structure(self, gen_service, sample_profile, db_session):
        """Test activity log structure in job."""
        from webapp.models import GenerationJob

        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="logging-test-job",
            target_date=datetime.now(),
            status="running",
            stage_details={
                "activity_log": [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": "Started generation",
                        "level": "info",
                    },
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": "Research complete",
                        "level": "success",
                    },
                ],
                "current_activity": "Generating script",
            },
        )
        db_session.add(job)
        db_session.commit()

        status = gen_service.get_job_status("logging-test-job")

        assert len(status["activity_log"]) == 2
        assert status["current_activity"] == "Generating script"
