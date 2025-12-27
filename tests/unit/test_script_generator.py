"""
Unit tests for script generators.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.mark.unit
class TestDialogueModels:
    """Tests for dialogue data models."""

    def test_dialogue_line_creation(self):
        """Test creating a dialogue line."""
        from src.generators import DialogueLine

        line = DialogueLine(
            speaker="raj",
            text="Hello everyone, welcome to the show!",
            emotion="excited",
        )

        assert line.speaker == "raj"
        assert "welcome" in line.text
        assert line.emotion == "excited"

    def test_dialogue_line_without_emotion(self):
        """Test dialogue line without emotion."""
        from src.generators import DialogueLine

        line = DialogueLine(speaker="priya", text="That's interesting!")

        assert line.speaker == "priya"
        assert line.emotion is None

    def test_podcast_segment_creation(self):
        """Test creating a podcast segment."""
        from src.generators import PodcastSegment, DialogueLine

        segment = PodcastSegment(
            topic_id="topic-1",
            topic_title="Breaking News",
            duration_estimate=180,
            dialogue=[
                DialogueLine(speaker="raj", text="Let's discuss this."),
                DialogueLine(speaker="priya", text="Yes, it's important."),
            ],
        )

        assert segment.topic_id == "topic-1"
        assert len(segment.dialogue) == 2
        assert segment.duration_estimate == 180


@pytest.mark.unit
class TestPodcastScript:
    """Tests for PodcastScript model."""

    def test_script_creation(self, sample_script):
        """Test creating a full podcast script."""
        assert sample_script.episode_id == "test-script-001"
        assert len(sample_script.intro) == 2
        assert len(sample_script.segments) == 1
        assert len(sample_script.outro) == 2

    def test_script_to_ssml_blocks(self, sample_script):
        """Test converting script to SSML blocks."""
        blocks = sample_script.to_ssml_blocks()

        assert len(blocks) > 0
        assert all("speaker" in block for block in blocks)
        assert all("text" in block for block in blocks)
        assert all("section" in block for block in blocks)

        # Check intro blocks
        intro_blocks = [b for b in blocks if b["section"] == "intro"]
        assert len(intro_blocks) == 2

        # Check outro blocks
        outro_blocks = [b for b in blocks if b["section"] == "outro"]
        assert len(outro_blocks) == 2


@pytest.mark.unit
class TestScriptGenerator:
    """Tests for ScriptGenerator class."""

    @pytest.fixture
    def mock_genai(self):
        """Mock google.generativeai module."""
        with patch("src.generators.script_generator.genai") as mock:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = MagicMock(
                text="""{
                    "intro": [{"speaker": "raj", "text": "Welcome!"}],
                    "segments": [
                        {
                            "topic_id": "topic-1",
                            "topic_title": "Test Topic",
                            "dialogue": [{"speaker": "priya", "text": "Interesting!"}]
                        }
                    ],
                    "outro": [{"speaker": "raj", "text": "Goodbye!"}]
                }"""
            )
            mock.GenerativeModel.return_value = mock_model
            yield mock

    def test_generator_initialization(self, mock_genai):
        """Test ScriptGenerator initialization."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")

        assert generator.model_name == "gemini-2.0-flash"
        mock_genai.configure.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_script(self, mock_genai, sample_topics):
        """Test script generation."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        script = await generator.generate_script(
            topics=sample_topics,
            episode_date=datetime.now(),
            target_duration_minutes=10,
            podcast_name="Test Podcast",
        )

        assert script is not None
        assert script.episode_id is not None
        assert len(script.intro) > 0

    def test_format_topics_for_prompt(self, mock_genai, sample_topics):
        """Test topic formatting for prompt."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        formatted = generator._format_topics_for_prompt(sample_topics)

        assert "Breaking: New Tech Announcement" in formatted
        assert "BREAKING" in formatted
        assert "tech" in formatted.lower()

    def test_parse_response_valid_json(self, mock_genai):
        """Test parsing valid JSON response."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        response = '{"intro": [], "segments": [], "outro": []}'
        result = generator._parse_response(response)

        assert "intro" in result
        assert "segments" in result
        assert "outro" in result

    def test_parse_response_with_code_blocks(self, mock_genai):
        """Test parsing JSON with markdown code blocks."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        response = '```json\n{"intro": [], "segments": [], "outro": []}\n```'
        result = generator._parse_response(response)

        assert "intro" in result
        assert "segments" in result

    def test_parse_response_invalid_json(self, mock_genai):
        """Test parsing invalid JSON returns empty structure."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        response = "not valid json at all"
        result = generator._parse_response(response)

        assert result == {"intro": [], "segments": [], "outro": []}

    def test_generate_episode_title(self, mock_genai, sample_topics):
        """Test episode title generation."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        title = generator._generate_episode_title(
            topics=sample_topics,
            episode_date=datetime(2024, 12, 25),
            podcast_name="Test Podcast",
        )

        assert "Test Podcast" in title
        assert "Dec 25" in title

    def test_generate_episode_title_with_breaking_news(self, mock_genai, sample_topics):
        """Test title prioritizes breaking news."""
        from src.generators.script_generator import ScriptGenerator

        generator = ScriptGenerator(api_key="test-key")
        title = generator._generate_episode_title(
            topics=sample_topics,
            episode_date=datetime.now(),
            podcast_name="Daily News",
        )

        # Should use the breaking news topic
        assert "Breaking" in title or "New Tech Announcement" in title


@pytest.mark.unit
class TestEnhancedScriptGenerator:
    """Tests for EnhancedScriptGenerator class."""

    @pytest.fixture
    def mock_genai_enhanced(self):
        """Mock for enhanced generator."""
        with patch("src.generators.enhanced_script_generator.genai") as mock:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = MagicMock(
                text="""{
                    "intro": [{"speaker": "raj", "text": "Welcome to today's show!"}],
                    "segments": [
                        {
                            "topic_id": "topic-1",
                            "topic_title": "Deep Dive Topic",
                            "dialogue": [
                                {"speaker": "raj", "text": "Let me share some facts."},
                                {"speaker": "priya", "text": "That's fascinating!"}
                            ]
                        }
                    ],
                    "outro": [{"speaker": "priya", "text": "Thanks for listening!"}]
                }"""
            )
            mock.GenerativeModel.return_value = mock_model
            yield mock

    def test_format_research_for_prompt(self, mock_genai_enhanced):
        """Test formatting research data for prompt."""
        from src.generators.enhanced_script_generator import EnhancedScriptGenerator
        from src.research.topic_researcher import TopicResearch, ResearchedFact, ExpertOpinion

        generator = EnhancedScriptGenerator(api_key="test-key")

        research = TopicResearch(
            topic_title="Test Topic",
            key_facts=[
                ResearchedFact(fact="Fact 1", source="Source 1", confidence=0.9),
                ResearchedFact(fact="Fact 2", source="Source 2", confidence=0.8),
            ],
            statistics=["Stat 1", "Stat 2"],
            historical_context="Some history",
            current_situation="Current state",
            future_implications="Future outlook",
            expert_opinions=[
                ExpertOpinion(person="Dr. Smith", role="Expert", quote="Important quote"),
            ],
            community_reactions=["Reaction 1"],
            common_misconceptions=["Misconception 1"],
            practical_advice=["Advice 1"],
            related_stories=["Story 1"],
            arguments_for=["Argument for"],
            arguments_against=["Argument against"],
            nuanced_take="Balanced view",
        )

        formatted = generator._format_research_for_prompt([research])

        assert "Test Topic" in formatted
        assert "Fact 1" in formatted
        assert "Dr. Smith" in formatted
        assert "KEY FACTS" in formatted
