"""
Agentic Content Intelligence Engine

A Google-first, multi-source content aggregation and research pipeline
for generating high-quality podcast content.

Pipeline stages:
1. Aggregation - Multi-source content fetching (Reddit, HN, News, RSS, YouTube)
2. Clustering - Semantic clustering with local embeddings
3. Research - Google Deep Research + Exa counter-arguments
4. Synthesis - Script generation with Gemini
5. Audio - Segment-based TTS with Gemini Native TTS
"""

# Core models
from .models.content import RawContent, TopicCluster, SourceConfig, ProfileSourceConfig
from .models.research import (
    ResearchedTopic,
    VerifiedFact,
    VerifiedTopic,
    EpisodeResearchBundle,
)

# Aggregation
from .aggregation.source_manager import (
    SourceManager,
    create_tech_source_manager,
    create_finance_source_manager,
    create_immigration_source_manager,
)

# Clustering
from .clustering.clusterer import SemanticClusterer
from .clustering.embedder import SemanticEmbedder
from .clustering.topic_namer import TopicNamer

# Research
from .research.google_researcher import GoogleResearcher, ResearchDepth
from .research.exa_researcher import ExaResearcher
from .research.research_orchestrator import ResearchOrchestrator

# Synthesis
from .synthesis.script_generator import ScriptGenerator, PodcastScript, ScriptSegment
from .synthesis.episode_synthesizer import EpisodeSynthesizer, create_episode

# Audio
from .audio.tts_generator import TTSGenerator, AudioEpisode, AudioSegment
from .audio.audio_stitcher import AudioStitcher

__all__ = [
    # Models
    "RawContent",
    "TopicCluster",
    "SourceConfig",
    "ProfileSourceConfig",
    "ResearchedTopic",
    "VerifiedFact",
    "VerifiedTopic",
    "EpisodeResearchBundle",
    # Aggregation
    "SourceManager",
    "create_tech_source_manager",
    "create_finance_source_manager",
    "create_immigration_source_manager",
    # Clustering
    "SemanticClusterer",
    "SemanticEmbedder",
    "TopicNamer",
    # Research
    "GoogleResearcher",
    "ResearchDepth",
    "ExaResearcher",
    "ResearchOrchestrator",
    # Synthesis
    "ScriptGenerator",
    "PodcastScript",
    "ScriptSegment",
    "EpisodeSynthesizer",
    "create_episode",
    # Audio
    "TTSGenerator",
    "AudioEpisode",
    "AudioSegment",
    "AudioStitcher",
]
