"""
Desi Podcast Engine - FastAPI Service
Main entry point for the podcast generation service
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from src.podcast_engine import PodcastEngine, EpisodeMetadata, create_engine_from_env
from src.rss_generator import RSSGenerator, PodcastFeedConfig

# Load environment variables
load_dotenv()

# Global engine instance
engine: Optional[PodcastEngine] = None
rss_generator: Optional[RSSGenerator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup"""
    global engine, rss_generator

    print("🎙️  Initializing Desi Podcast Engine...")

    try:
        engine = await create_engine_from_env()
        rss_generator = RSSGenerator()
        print("✅ Engine initialized successfully")
    except Exception as e:
        print(f"⚠️  Engine initialization failed: {e}")
        print("   Some features may not work without valid API keys.")

    yield

    print("👋 Shutting down Desi Podcast Engine...")


# Create FastAPI app
app = FastAPI(
    title="Desi Podcast Engine",
    description="AI-powered daily podcast generator for the South Asian diaspora in the USA",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class GenerateRequest(BaseModel):
    topic_count: int = 5
    target_duration_minutes: int = 12
    generate_audio: bool = True
    target_date: Optional[str] = None  # ISO format


class ContentPreview(BaseModel):
    date: str
    topic_count: int
    topics: list[dict]


class GenerationStatus(BaseModel):
    status: str
    episode_id: Optional[str] = None
    message: str


# Background task tracking
generation_tasks: dict[str, GenerationStatus] = {}


# Routes
@app.get("/")
async def root():
    """Service health check"""
    return {
        "service": "Desi Podcast Engine",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "engine_initialized": engine is not None,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/preview", response_model=ContentPreview)
async def get_content_preview():
    """Preview today's content without generating"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    preview = await engine.get_content_preview()
    return preview


@app.post("/generate", response_model=GenerationStatus)
async def generate_episode(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate a new podcast episode

    This starts generation in the background and returns immediately.
    Use /status/{episode_id} to check progress.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    # Parse target date
    target_date = None
    if request.target_date:
        try:
            target_date = datetime.fromisoformat(request.target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    # Generate episode ID
    date_for_id = target_date or datetime.now()
    episode_id = f"dd-{date_for_id.strftime('%Y%m%d')}"

    # Check if already generating
    if episode_id in generation_tasks:
        existing = generation_tasks[episode_id]
        if existing.status == "generating":
            return existing

    # Start background generation
    generation_tasks[episode_id] = GenerationStatus(
        status="generating",
        episode_id=episode_id,
        message="Episode generation started",
    )

    async def generate_in_background():
        try:
            await engine.generate_episode(
                target_date=target_date,
                topic_count=request.topic_count,
                target_duration_minutes=request.target_duration_minutes,
                generate_audio=request.generate_audio,
            )
            generation_tasks[episode_id] = GenerationStatus(
                status="completed",
                episode_id=episode_id,
                message="Episode generated successfully",
            )
        except Exception as e:
            generation_tasks[episode_id] = GenerationStatus(
                status="failed",
                episode_id=episode_id,
                message=f"Generation failed: {str(e)}",
            )

    background_tasks.add_task(generate_in_background)

    return generation_tasks[episode_id]


@app.get("/status/{episode_id}", response_model=GenerationStatus)
async def get_generation_status(episode_id: str):
    """Check the status of an episode generation"""
    if episode_id in generation_tasks:
        return generation_tasks[episode_id]

    # Check if episode exists
    if engine:
        episode = engine.get_episode(episode_id)
        if episode:
            return GenerationStatus(
                status="completed",
                episode_id=episode_id,
                message="Episode available",
            )

    return GenerationStatus(
        status="not_found",
        episode_id=episode_id,
        message="Episode not found or generation not started",
    )


@app.get("/episodes")
async def list_episodes(limit: int = Query(default=10, le=50)):
    """List all generated episodes"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    episodes = engine.list_episodes()
    return {
        "count": len(episodes),
        "episodes": [ep.model_dump() for ep in episodes[:limit]],
    }


@app.get("/episodes/{episode_id}")
async def get_episode(episode_id: str):
    """Get details of a specific episode"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    episode = engine.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    return episode.model_dump()


@app.get("/episodes/{episode_id}/audio")
async def get_episode_audio(episode_id: str):
    """Download episode audio file"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    episode = engine.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    if not episode.audio_path or not Path(episode.audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        episode.audio_path,
        media_type="audio/mpeg",
        filename=f"{episode_id}.mp3",
    )


@app.get("/episodes/{episode_id}/script")
async def get_episode_script(episode_id: str):
    """Get episode script JSON"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    episode = engine.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    if not episode.script_path or not Path(episode.script_path).exists():
        raise HTTPException(status_code=404, detail="Script file not found")

    return FileResponse(
        episode.script_path,
        media_type="application/json",
        filename=f"{episode_id}_script.json",
    )


@app.get("/feed.xml")
async def get_rss_feed():
    """Get the podcast RSS feed"""
    if not engine or not rss_generator:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    episodes = engine.list_episodes()

    # Filter to episodes with audio
    episodes_with_audio = [ep for ep in episodes if ep.audio_path]

    feed_xml = rss_generator.generate_feed(episodes_with_audio)

    return Response(
        content=feed_xml,
        media_type="application/xml",
    )


@app.post("/generate-script-only")
async def generate_script_only(request: GenerateRequest):
    """Generate only the script (no audio) - faster for testing"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    target_date = None
    if request.target_date:
        target_date = datetime.fromisoformat(request.target_date)

    script = await engine.generate_script_only(
        target_date=target_date,
        topic_count=request.topic_count,
        target_duration_minutes=request.target_duration_minutes,
    )

    return {
        "episode_id": script.episode_id,
        "title": script.episode_title,
        "duration_estimate": script.duration_estimate,
        "segment_count": len(script.segments),
        "script": script.model_dump(),
    }


# CLI entry point
def main():
    """Run the server"""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    print(f"""
    ╔═══════════════════════════════════════════════════════╗
    ║           🎙️  DESI PODCAST ENGINE  🎙️                ║
    ╠═══════════════════════════════════════════════════════╣
    ║  AI-powered daily podcast for the South Asian         ║
    ║  immigrant community in America                       ║
    ╠═══════════════════════════════════════════════════════╣
    ║  Server: http://{host}:{port}                         ║
    ║  Docs:   http://{host}:{port}/docs                    ║
    ║  Feed:   http://{host}:{port}/feed.xml                ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
    )


if __name__ == "__main__":
    main()
