"""Studio Dashboard API - Full podcast management interface."""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# Job tracking
generation_jobs: dict = {}


class GenerationRequest(BaseModel):
    """Request to generate a new podcast."""
    profile: str = "tech"
    name: str = "Tech Daily"
    max_topics: int = 3
    quick_mode: bool = False
    generate_audio: bool = True


class GenerationJob(BaseModel):
    """Status of a generation job."""
    job_id: str
    status: str  # pending, running, completed, failed
    profile: str
    name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    progress: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    yield


def create_app(episodes_dir: str = "./output") -> FastAPI:
    """Create the studio dashboard app."""

    app = FastAPI(
        title="PodcastOS Studio",
        description="AI-Powered Podcast Generation Dashboard",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount audio files
    output_path = Path(episodes_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=str(output_path)), name="audio")

    return app


app = create_app()


# ============== Dashboard HTML ==============

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PodcastOS Studio</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-card: rgba(255, 255, 255, 0.03);
            --accent-cyan: #00d4ff;
            --accent-purple: #7b2cbf;
            --accent-green: #00ff88;
            --text-primary: #ffffff;
            --text-secondary: #888;
            --border: rgba(255, 255, 255, 0.1);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .layout {
            display: flex;
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 250px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-icon {
            font-size: 1.8rem;
        }

        .nav-section {
            margin-bottom: 25px;
        }

        .nav-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            margin-bottom: 10px;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 15px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 5px;
        }

        .nav-item:hover {
            background: var(--bg-card);
        }

        .nav-item.active {
            background: rgba(0, 212, 255, 0.15);
            color: var(--accent-cyan);
        }

        .nav-icon {
            font-size: 1.2rem;
        }

        /* Main Content */
        .main {
            flex: 1;
            margin-left: 250px;
            padding: 30px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }

        .page-title {
            font-size: 1.8rem;
            font-weight: 600;
        }

        .btn {
            padding: 12px 24px;
            border-radius: 10px;
            border: none;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.3);
        }

        .btn-secondary {
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .stat-label {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        .stat-card.cyan .stat-value { color: var(--accent-cyan); }
        .stat-card.purple .stat-value { color: var(--accent-purple); }
        .stat-card.green .stat-value { color: var(--accent-green); }

        /* Episodes Table */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
        }

        .card-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
        }

        .episodes-table {
            width: 100%;
        }

        .episodes-table th,
        .episodes-table td {
            padding: 15px 20px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        .episodes-table th {
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .episodes-table tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .episode-title {
            font-weight: 500;
        }

        .episode-meta {
            color: var(--text-secondary);
            font-size: 0.85rem;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .badge-tech { background: rgba(0, 212, 255, 0.2); color: var(--accent-cyan); }
        .badge-finance { background: rgba(0, 255, 136, 0.2); color: var(--accent-green); }
        .badge-immigration { background: rgba(123, 44, 191, 0.2); color: var(--accent-purple); }

        .action-btn {
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: none;
            color: var(--text-primary);
            cursor: pointer;
            margin-right: 8px;
            transition: all 0.2s;
        }

        .action-btn:hover {
            background: var(--bg-card);
        }

        /* Generate Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            display: none;
        }

        .modal-overlay.active {
            display: flex;
        }

        .modal {
            background: var(--bg-secondary);
            border-radius: 20px;
            width: 100%;
            max-width: 500px;
            padding: 30px;
            border: 1px solid var(--border);
        }

        .modal-title {
            font-size: 1.3rem;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        .form-input,
        .form-select {
            width: 100%;
            padding: 12px 15px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text-primary);
            font-size: 1rem;
        }

        .form-input:focus,
        .form-select:focus {
            outline: none;
            border-color: var(--accent-cyan);
        }

        .form-checkbox {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 25px;
        }

        .modal-actions .btn {
            flex: 1;
        }

        /* Loading */
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }

        .empty-icon {
            font-size: 3rem;
            margin-bottom: 15px;
        }

        /* Progress indicator */
        .progress-bar {
            height: 4px;
            background: var(--border);
            border-radius: 2px;
            overflow: hidden;
            margin-top: 15px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
            width: 0%;
            animation: progress 2s ease-in-out infinite;
        }

        @keyframes progress {
            0% { width: 0%; }
            50% { width: 70%; }
            100% { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="layout">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="logo">
                <span class="logo-icon">🎙️</span>
                <span>PodcastOS</span>
            </div>

            <nav>
                <div class="nav-section">
                    <div class="nav-title">Dashboard</div>
                    <div class="nav-item active" onclick="showSection('episodes')">
                        <span class="nav-icon">📻</span>
                        <span>Episodes</span>
                    </div>
                    <div class="nav-item" onclick="showSection('analytics')">
                        <span class="nav-icon">📊</span>
                        <span>Analytics</span>
                    </div>
                </div>

                <div class="nav-section">
                    <div class="nav-title">Settings</div>
                    <div class="nav-item" onclick="showSection('profiles')">
                        <span class="nav-icon">👤</span>
                        <span>Profiles</span>
                    </div>
                    <div class="nav-item" onclick="showSection('sources')">
                        <span class="nav-icon">🔗</span>
                        <span>Sources</span>
                    </div>
                    <div class="nav-item" onclick="showSection('voices')">
                        <span class="nav-icon">🎤</span>
                        <span>Voices</span>
                    </div>
                </div>
            </nav>
        </aside>

        <!-- Main Content -->
        <main class="main">
            <div class="header">
                <h1 class="page-title">Episodes</h1>
                <button class="btn btn-primary" onclick="openGenerateModal()">
                    <span>✨</span> Generate New
                </button>
            </div>

            <!-- Stats -->
            <div class="stats-grid">
                <div class="stat-card cyan">
                    <div class="stat-value" id="stat-episodes">0</div>
                    <div class="stat-label">Total Episodes</div>
                </div>
                <div class="stat-card purple">
                    <div class="stat-value" id="stat-duration">0m</div>
                    <div class="stat-label">Total Duration</div>
                </div>
                <div class="stat-card green">
                    <div class="stat-value" id="stat-segments">0</div>
                    <div class="stat-label">Total Segments</div>
                </div>
            </div>

            <!-- Episodes List -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Recent Episodes</span>
                </div>
                <div id="episodes-container">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading episodes...
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Generate Modal -->
    <div class="modal-overlay" id="generate-modal">
        <div class="modal">
            <h2 class="modal-title">Generate New Episode</h2>

            <div class="form-group">
                <label class="form-label">Podcast Name</label>
                <input type="text" class="form-input" id="podcast-name" value="Tech Daily" placeholder="Enter podcast name">
            </div>

            <div class="form-group">
                <label class="form-label">Profile</label>
                <select class="form-select" id="podcast-profile">
                    <option value="tech">Tech News</option>
                    <option value="finance">Finance</option>
                    <option value="immigration">Immigration</option>
                </select>
            </div>

            <div class="form-group">
                <label class="form-label">Max Topics</label>
                <select class="form-select" id="max-topics">
                    <option value="2">2 topics (~4 min)</option>
                    <option value="3" selected>3 topics (~6 min)</option>
                    <option value="5">5 topics (~10 min)</option>
                    <option value="7">7 topics (~15 min)</option>
                </select>
            </div>

            <div class="form-group">
                <label class="form-checkbox">
                    <input type="checkbox" id="quick-mode">
                    Quick Mode (faster, less research)
                </label>
            </div>

            <div class="form-group">
                <label class="form-checkbox">
                    <input type="checkbox" id="generate-audio" checked>
                    Generate Audio
                </label>
            </div>

            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeGenerateModal()">Cancel</button>
                <button class="btn btn-primary" onclick="startGeneration()">Generate</button>
            </div>

            <div id="generation-progress" style="display: none;">
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
                <p id="progress-text" style="text-align: center; margin-top: 10px; color: var(--text-secondary);">
                    Generating podcast...
                </p>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '';

        // Load episodes on page load
        async function loadEpisodes() {
            try {
                const response = await fetch(`${API_BASE}/api/studio/episodes`);
                const data = await response.json();

                updateStats(data.stats);
                renderEpisodes(data.episodes);
            } catch (error) {
                console.error('Failed to load episodes:', error);
                document.getElementById('episodes-container').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🎙️</div>
                        <p>No episodes yet. Click "Generate New" to create your first podcast!</p>
                    </div>
                `;
            }
        }

        function updateStats(stats) {
            document.getElementById('stat-episodes').textContent = stats.total_episodes;
            document.getElementById('stat-duration').textContent = `${Math.round(stats.total_duration / 60)}m`;
            document.getElementById('stat-segments').textContent = stats.total_segments;
        }

        function renderEpisodes(episodes) {
            if (!episodes || episodes.length === 0) {
                document.getElementById('episodes-container').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🎙️</div>
                        <p>No episodes yet. Click "Generate New" to create your first podcast!</p>
                    </div>
                `;
                return;
            }

            document.getElementById('episodes-container').innerHTML = `
                <table class="episodes-table">
                    <thead>
                        <tr>
                            <th>Episode</th>
                            <th>Profile</th>
                            <th>Duration</th>
                            <th>Segments</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${episodes.map(ep => `
                            <tr>
                                <td>
                                    <div class="episode-title">${ep.title}</div>
                                    <div class="episode-meta">${ep.episode_id}</div>
                                </td>
                                <td><span class="badge badge-${ep.profile || 'tech'}">${ep.profile || 'tech'}</span></td>
                                <td>${formatDuration(ep.total_duration_seconds)}</td>
                                <td>${ep.segments}</td>
                                <td>${formatDate(ep.generated_at)}</td>
                                <td>
                                    <button class="action-btn" onclick="playEpisode('${ep.episode_id}')" title="Play">▶️</button>
                                    <button class="action-btn" onclick="openPlayer('${ep.episode_id}')" title="Open Player">🎧</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        function formatDuration(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        }

        function formatDate(dateStr) {
            const date = new Date(dateStr);
            return date.toLocaleDateString();
        }

        // Modal functions
        function openGenerateModal() {
            document.getElementById('generate-modal').classList.add('active');
        }

        function closeGenerateModal() {
            document.getElementById('generate-modal').classList.remove('active');
            document.getElementById('generation-progress').style.display = 'none';
        }

        async function startGeneration() {
            const name = document.getElementById('podcast-name').value;
            const profile = document.getElementById('podcast-profile').value;
            const maxTopics = parseInt(document.getElementById('max-topics').value);
            const quickMode = document.getElementById('quick-mode').checked;
            const generateAudio = document.getElementById('generate-audio').checked;

            document.getElementById('generation-progress').style.display = 'block';

            try {
                const response = await fetch(`${API_BASE}/api/studio/generate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        profile,
                        name,
                        max_topics: maxTopics,
                        quick_mode: quickMode,
                        generate_audio: generateAudio
                    })
                });

                const result = await response.json();

                if (result.success) {
                    document.getElementById('progress-text').textContent = 'Episode generated successfully!';
                    setTimeout(() => {
                        closeGenerateModal();
                        loadEpisodes();
                    }, 1500);
                } else {
                    document.getElementById('progress-text').textContent = 'Generation failed: ' + (result.error || 'Unknown error');
                }
            } catch (error) {
                document.getElementById('progress-text').textContent = 'Error: ' + error.message;
            }
        }

        function playEpisode(episodeId) {
            // Play audio directly
            window.open(`/audio/${episodeId}_complete.wav`, '_blank');
        }

        function openPlayer(episodeId) {
            window.open('/player', '_blank');
        }

        function showSection(section) {
            // Update nav
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
            event.currentTarget.classList.add('active');

            // For now, just show episodes
            // Can expand to show other sections
        }

        // Initialize
        loadEpisodes();
    </script>
</body>
</html>
"""


# ============== API Endpoints ==============

@app.get("/")
async def root():
    """Redirect to dashboard."""
    return {"message": "PodcastOS Studio API", "dashboard": "/dashboard"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve studio dashboard."""
    return DASHBOARD_HTML


@app.get("/api/studio/episodes")
async def list_studio_episodes():
    """List episodes with stats."""
    output_dir = Path(os.getenv("EPISODES_DIR", "./output"))

    episodes = []
    total_duration = 0
    total_segments = 0

    for manifest_path in output_dir.glob("*_manifest.json"):
        try:
            with open(manifest_path) as f:
                data = json.load(f)

            duration = data.get("total_duration_seconds", 0)
            segments = len(data.get("segments", []))

            episodes.append({
                "episode_id": data.get("episode_id"),
                "title": data.get("title"),
                "total_duration_seconds": duration,
                "segments": segments,
                "generated_at": data.get("generated_at"),
                "profile": "tech",  # Default for now
            })

            total_duration += duration
            total_segments += segments

        except Exception as e:
            print(f"Error loading {manifest_path}: {e}")

    # Sort by date, newest first
    episodes.sort(key=lambda x: x.get("generated_at", ""), reverse=True)

    return {
        "episodes": episodes,
        "stats": {
            "total_episodes": len(episodes),
            "total_duration": total_duration,
            "total_segments": total_segments,
        }
    }


@app.post("/api/studio/generate")
async def generate_episode(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Generate a new podcast episode."""
    from src.intelligence.pipeline import run_pipeline

    try:
        result = await run_pipeline(
            profile_type=request.profile,
            podcast_name=request.name,
            max_topics=request.max_topics,
            quick_mode=request.quick_mode,
            generate_audio=request.generate_audio,
            output_dir=os.getenv("EPISODES_DIR", "./output"),
        )

        return {
            "success": result.get("success", False),
            "episode_id": result.get("script_path", "").split("/")[-1].replace("_script.json", ""),
            "audio_path": result.get("audio_path"),
            "error": result.get("errors"),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@app.get("/api/studio/status")
async def studio_status():
    """Get studio status."""
    gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    return {
        "status": "ready" if gemini_key else "missing_api_key",
        "api_keys": {
            "gemini": bool(gemini_key),
            "newsdata": bool(os.getenv("NEWSDATA_API_KEY")),
            "reddit": bool(os.getenv("REDDIT_CLIENT_ID")),
        }
    }


# Include player routes
@app.get("/player", response_class=HTMLResponse)
async def player_redirect():
    """Redirect to player API."""
    from .dashboard_api import app
    # Import player HTML
    from src.player.api import PLAYER_HTML
    return PLAYER_HTML
