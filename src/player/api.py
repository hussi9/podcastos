"""FastAPI backend for the interactive podcast player."""

import os
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .player_service import (
    PlayerService,
    EpisodeInfo,
    SegmentInfo,
    PlaybackState,
    DeepDiveRequest,
    DeepDiveResponse,
)


# Global player service
player_service: Optional[PlayerService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize player service on startup."""
    global player_service

    episodes_dir = os.getenv("EPISODES_DIR", "./output")
    player_service = PlayerService(episodes_dir)
    player_service.scan_episodes()

    yield

    # Cleanup if needed
    player_service = None


def create_app(episodes_dir: str = "./output") -> FastAPI:
    """Create FastAPI app with configuration."""

    app = FastAPI(
        title="PodcastOS Player API",
        description="Interactive podcast player with skip and deep-dive features",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS for web player
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files for audio
    output_path = Path(episodes_dir)
    if output_path.exists():
        app.mount("/audio", StaticFiles(directory=str(output_path)), name="audio")

    return app


# Create default app
app = create_app()


# ============== API Endpoints ==============

@app.get("/")
async def root():
    """API root with info."""
    return {
        "name": "PodcastOS Player API",
        "version": "1.0.0",
        "endpoints": {
            "episodes": "/api/episodes",
            "player": "/player",
        }
    }


@app.get("/api/episodes", response_model=list[EpisodeInfo])
async def list_episodes():
    """List all available episodes."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    episodes = player_service.list_episodes()

    # Add URLs for audio files
    for episode in episodes:
        if episode.combined_file_path:
            filename = Path(episode.combined_file_path).name
            episode.combined_file_url = f"/audio/{filename}"

        for segment in episode.segments:
            # Get relative path for URL
            segment.file_url = f"/audio/{Path(segment.file_path).parent.name}/{Path(segment.file_path).name}"

    return episodes


@app.get("/api/episodes/{episode_id}", response_model=EpisodeInfo)
async def get_episode(episode_id: str):
    """Get episode details."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    episode = player_service.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    # Add URLs
    if episode.combined_file_path:
        filename = Path(episode.combined_file_path).name
        episode.combined_file_url = f"/audio/{filename}"

    for segment in episode.segments:
        segment.file_url = f"/audio/{Path(segment.file_path).parent.name}/{Path(segment.file_path).name}"

    return episode


@app.get("/api/episodes/{episode_id}/segments", response_model=list[SegmentInfo])
async def get_segments(episode_id: str):
    """Get segments for an episode."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    episode = player_service.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    return episode.segments


@app.get("/api/episodes/{episode_id}/state", response_model=PlaybackState)
async def get_playback_state(episode_id: str):
    """Get current playback state."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return player_service.get_playback_state(episode_id)


class UpdateStateRequest(BaseModel):
    segment_index: Optional[int] = None
    time_seconds: Optional[float] = None
    is_playing: Optional[bool] = None
    playback_rate: Optional[float] = None


@app.post("/api/episodes/{episode_id}/state", response_model=PlaybackState)
async def update_playback_state(episode_id: str, request: UpdateStateRequest):
    """Update playback state."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return player_service.update_playback_state(
        episode_id,
        segment_index=request.segment_index,
        time_seconds=request.time_seconds,
        is_playing=request.is_playing,
        playback_rate=request.playback_rate,
    )


@app.post("/api/episodes/{episode_id}/skip/{segment_index}", response_model=PlaybackState)
async def skip_to_segment(episode_id: str, segment_index: int):
    """Skip to a specific segment."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return player_service.skip_to_segment(episode_id, segment_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/episodes/{episode_id}/next", response_model=PlaybackState)
async def next_segment(episode_id: str):
    """Skip to next segment."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    state = player_service.next_segment(episode_id)
    if not state:
        raise HTTPException(status_code=400, detail="Already at end of episode")
    return state


@app.post("/api/episodes/{episode_id}/previous", response_model=PlaybackState)
async def previous_segment(episode_id: str):
    """Skip to previous segment."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    state = player_service.previous_segment(episode_id)
    if not state:
        raise HTTPException(status_code=400, detail="Already at start of episode")
    return state


@app.post("/api/deep-dive", response_model=DeepDiveResponse)
async def deep_dive(request: DeepDiveRequest):
    """Generate deep-dive content for a segment."""
    if not player_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return await player_service.generate_deep_dive(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== Web Player ==============

PLAYER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PodcastOS Player</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            text-align: center;
            padding: 40px 0;
        }

        header h1 {
            font-size: 2.5rem;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }

        header p {
            color: #888;
            font-size: 1.1rem;
        }

        .episode-list {
            margin-bottom: 30px;
        }

        .episode-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .episode-card:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }

        .episode-card.active {
            border-color: #00d4ff;
            background: rgba(0, 212, 255, 0.1);
        }

        .episode-title {
            font-size: 1.3rem;
            margin-bottom: 8px;
        }

        .episode-meta {
            color: #888;
            font-size: 0.9rem;
        }

        .player-container {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .now-playing {
            text-align: center;
            margin-bottom: 20px;
        }

        .now-playing h2 {
            font-size: 1.5rem;
            margin-bottom: 5px;
        }

        .now-playing .segment-title {
            color: #00d4ff;
            font-size: 1.1rem;
        }

        .progress-container {
            margin: 20px 0;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            cursor: pointer;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            border-radius: 3px;
            width: 0%;
            transition: width 0.1s linear;
        }

        .time-display {
            display: flex;
            justify-content: space-between;
            color: #888;
            font-size: 0.85rem;
            margin-top: 8px;
        }

        .controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            margin: 25px 0;
        }

        .control-btn {
            background: none;
            border: none;
            color: #fff;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 15px;
            border-radius: 50%;
            transition: all 0.2s ease;
        }

        .control-btn:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .control-btn.play-pause {
            background: linear-gradient(135deg, #00d4ff, #7b2cbf);
            font-size: 2rem;
            padding: 20px;
        }

        .control-btn.play-pause:hover {
            transform: scale(1.1);
        }

        .segments-list {
            margin-top: 30px;
        }

        .segments-list h3 {
            margin-bottom: 15px;
            color: #888;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .segment-item {
            display: flex;
            align-items: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .segment-item:hover {
            background: rgba(255, 255, 255, 0.08);
        }

        .segment-item.active {
            background: rgba(0, 212, 255, 0.15);
            border-left: 3px solid #00d4ff;
        }

        .segment-item.playing {
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .segment-number {
            width: 30px;
            height: 30px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            font-size: 0.85rem;
        }

        .segment-info {
            flex: 1;
        }

        .segment-name {
            font-size: 1rem;
            margin-bottom: 3px;
        }

        .segment-duration {
            color: #888;
            font-size: 0.85rem;
        }

        .segment-actions {
            display: flex;
            gap: 10px;
        }

        .action-btn {
            padding: 8px 16px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: none;
            color: #fff;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .action-btn:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .action-btn.deep-dive {
            border-color: #7b2cbf;
            color: #7b2cbf;
        }

        .action-btn.deep-dive:hover {
            background: rgba(123, 44, 191, 0.2);
        }

        .deep-dive-panel {
            background: rgba(123, 44, 191, 0.1);
            border: 1px solid rgba(123, 44, 191, 0.3);
            border-radius: 12px;
            padding: 20px;
            margin-top: 15px;
            display: none;
        }

        .deep-dive-panel.active {
            display: block;
        }

        .deep-dive-panel h4 {
            color: #7b2cbf;
            margin-bottom: 10px;
        }

        .deep-dive-content {
            color: #ccc;
            line-height: 1.6;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #888;
        }

        .speed-control {
            display: flex;
            align-items: center;
            gap: 10px;
            justify-content: center;
            margin-top: 15px;
        }

        .speed-btn {
            padding: 5px 12px;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: none;
            color: #888;
            font-size: 0.8rem;
            cursor: pointer;
        }

        .speed-btn.active {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border-color: #00d4ff;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>PodcastOS</h1>
            <p>Interactive AI-Powered Podcasts</p>
        </header>

        <div id="episode-list" class="episode-list">
            <div class="loading">Loading episodes...</div>
        </div>

        <div id="player" class="player-container" style="display: none;">
            <div class="now-playing">
                <h2 id="episode-title">Select an Episode</h2>
                <div class="segment-title" id="segment-title">-</div>
            </div>

            <div class="progress-container">
                <div class="progress-bar" id="progress-bar">
                    <div class="progress-fill" id="progress-fill"></div>
                </div>
                <div class="time-display">
                    <span id="current-time">0:00</span>
                    <span id="total-time">0:00</span>
                </div>
            </div>

            <div class="controls">
                <button class="control-btn" id="prev-btn" title="Previous Segment">⏮</button>
                <button class="control-btn" id="rewind-btn" title="Rewind 15s">↺</button>
                <button class="control-btn play-pause" id="play-btn">▶</button>
                <button class="control-btn" id="forward-btn" title="Forward 15s">↻</button>
                <button class="control-btn" id="next-btn" title="Next Segment">⏭</button>
            </div>

            <div class="speed-control">
                <span style="color: #888; font-size: 0.85rem;">Speed:</span>
                <button class="speed-btn" data-speed="0.75">0.75x</button>
                <button class="speed-btn active" data-speed="1">1x</button>
                <button class="speed-btn" data-speed="1.25">1.25x</button>
                <button class="speed-btn" data-speed="1.5">1.5x</button>
                <button class="speed-btn" data-speed="2">2x</button>
            </div>

            <div class="segments-list">
                <h3>Segments</h3>
                <div id="segments"></div>
            </div>
        </div>
    </div>

    <audio id="audio-player"></audio>

    <script>
        const API_BASE = '';
        let currentEpisode = null;
        let currentSegmentIndex = 0;
        let audioPlayer = document.getElementById('audio-player');

        // Format time as M:SS
        function formatTime(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        }

        // Load episodes
        async function loadEpisodes() {
            try {
                const response = await fetch(`${API_BASE}/api/episodes`);
                const episodes = await response.json();

                const container = document.getElementById('episode-list');

                if (episodes.length === 0) {
                    container.innerHTML = '<div class="loading">No episodes available</div>';
                    return;
                }

                container.innerHTML = episodes.map(ep => `
                    <div class="episode-card" data-id="${ep.episode_id}">
                        <div class="episode-title">${ep.title}</div>
                        <div class="episode-meta">
                            ${ep.segments.length} segments · ${formatTime(ep.total_duration_seconds)}
                        </div>
                    </div>
                `).join('');

                // Add click handlers
                container.querySelectorAll('.episode-card').forEach(card => {
                    card.addEventListener('click', () => selectEpisode(card.dataset.id));
                });

                // Auto-select first episode
                if (episodes.length > 0) {
                    selectEpisode(episodes[0].episode_id);
                }
            } catch (error) {
                console.error('Failed to load episodes:', error);
                document.getElementById('episode-list').innerHTML =
                    '<div class="loading">Failed to load episodes</div>';
            }
        }

        // Select and load episode
        async function selectEpisode(episodeId) {
            try {
                const response = await fetch(`${API_BASE}/api/episodes/${episodeId}`);
                currentEpisode = await response.json();
                currentSegmentIndex = 0;

                // Update UI
                document.querySelectorAll('.episode-card').forEach(card => {
                    card.classList.toggle('active', card.dataset.id === episodeId);
                });

                document.getElementById('player').style.display = 'block';
                document.getElementById('episode-title').textContent = currentEpisode.title;
                document.getElementById('total-time').textContent = formatTime(currentEpisode.total_duration_seconds);

                // Render segments
                renderSegments();

                // Load audio
                if (currentEpisode.combined_file_url) {
                    audioPlayer.src = currentEpisode.combined_file_url;
                }

                updateSegmentDisplay();
            } catch (error) {
                console.error('Failed to load episode:', error);
            }
        }

        // Render segments list
        function renderSegments() {
            const container = document.getElementById('segments');

            container.innerHTML = currentEpisode.segments.map((seg, index) => `
                <div class="segment-item" data-index="${index}">
                    <div class="segment-number">${index + 1}</div>
                    <div class="segment-info">
                        <div class="segment-name">${seg.title}</div>
                        <div class="segment-duration">${formatTime(seg.duration_seconds)}</div>
                    </div>
                    <div class="segment-actions">
                        ${seg.can_skip ? `<button class="action-btn" onclick="skipToSegment(${index})">Play</button>` : ''}
                        ${seg.can_deep_dive ? `<button class="action-btn deep-dive" onclick="deepDive('${seg.id}')">Deep Dive</button>` : ''}
                    </div>
                </div>
                <div class="deep-dive-panel" id="deep-dive-${seg.id}">
                    <h4>Deep Dive</h4>
                    <div class="deep-dive-content">Loading...</div>
                </div>
            `).join('');

            // Add click handlers for segment items
            container.querySelectorAll('.segment-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (!e.target.classList.contains('action-btn')) {
                        skipToSegment(parseInt(item.dataset.index));
                    }
                });
            });
        }

        // Update segment display
        function updateSegmentDisplay() {
            if (!currentEpisode) return;

            const segment = currentEpisode.segments[currentSegmentIndex];
            document.getElementById('segment-title').textContent = segment ? segment.title : '-';

            // Update active state
            document.querySelectorAll('.segment-item').forEach((item, index) => {
                item.classList.toggle('active', index === currentSegmentIndex);
                item.classList.toggle('playing', index === currentSegmentIndex && !audioPlayer.paused);
            });
        }

        // Skip to segment
        function skipToSegment(index) {
            if (!currentEpisode || index < 0 || index >= currentEpisode.segments.length) return;

            currentSegmentIndex = index;
            const segment = currentEpisode.segments[index];

            audioPlayer.currentTime = segment.start_time_seconds;
            audioPlayer.play();

            updateSegmentDisplay();
            updatePlayButton();
        }

        // Deep dive
        async function deepDive(segmentId) {
            const panel = document.getElementById(`deep-dive-${segmentId}`);

            if (panel.classList.contains('active')) {
                panel.classList.remove('active');
                return;
            }

            // Close other panels
            document.querySelectorAll('.deep-dive-panel').forEach(p => p.classList.remove('active'));

            panel.classList.add('active');
            panel.querySelector('.deep-dive-content').innerHTML = 'Loading deep dive...';

            try {
                const response = await fetch(`${API_BASE}/api/deep-dive`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        episode_id: currentEpisode.episode_id,
                        segment_id: segmentId
                    })
                });

                const data = await response.json();
                panel.querySelector('.deep-dive-content').innerHTML = data.deep_dive_text || 'No additional information available.';
            } catch (error) {
                panel.querySelector('.deep-dive-content').innerHTML = 'Failed to load deep dive content.';
            }
        }

        // Update play button
        function updatePlayButton() {
            document.getElementById('play-btn').textContent = audioPlayer.paused ? '▶' : '⏸';
        }

        // Player controls
        document.getElementById('play-btn').addEventListener('click', () => {
            if (audioPlayer.paused) {
                audioPlayer.play();
            } else {
                audioPlayer.pause();
            }
        });

        document.getElementById('prev-btn').addEventListener('click', () => {
            if (currentSegmentIndex > 0) {
                skipToSegment(currentSegmentIndex - 1);
            }
        });

        document.getElementById('next-btn').addEventListener('click', () => {
            if (currentEpisode && currentSegmentIndex < currentEpisode.segments.length - 1) {
                skipToSegment(currentSegmentIndex + 1);
            }
        });

        document.getElementById('rewind-btn').addEventListener('click', () => {
            audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 15);
        });

        document.getElementById('forward-btn').addEventListener('click', () => {
            audioPlayer.currentTime = Math.min(audioPlayer.duration, audioPlayer.currentTime + 15);
        });

        // Progress bar
        document.getElementById('progress-bar').addEventListener('click', (e) => {
            const rect = e.target.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            audioPlayer.currentTime = percent * audioPlayer.duration;
        });

        // Speed control
        document.querySelectorAll('.speed-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const speed = parseFloat(btn.dataset.speed);
                audioPlayer.playbackRate = speed;
                document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        // Audio events
        audioPlayer.addEventListener('play', updatePlayButton);
        audioPlayer.addEventListener('pause', updatePlayButton);

        audioPlayer.addEventListener('timeupdate', () => {
            if (!currentEpisode) return;

            const current = audioPlayer.currentTime;
            const duration = audioPlayer.duration || currentEpisode.total_duration_seconds;

            document.getElementById('current-time').textContent = formatTime(current);
            document.getElementById('progress-fill').style.width = `${(current / duration) * 100}%`;

            // Update current segment based on time
            for (let i = currentEpisode.segments.length - 1; i >= 0; i--) {
                if (current >= currentEpisode.segments[i].start_time_seconds) {
                    if (i !== currentSegmentIndex) {
                        currentSegmentIndex = i;
                        updateSegmentDisplay();
                    }
                    break;
                }
            }
        });

        // Initialize
        loadEpisodes();
    </script>
</body>
</html>
"""


@app.get("/player", response_class=HTMLResponse)
async def player_page():
    """Serve the web player."""
    return PLAYER_HTML


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "PodcastOS Player"}
