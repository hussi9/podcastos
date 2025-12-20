"""
PodcastOS - Complete Web Application

A production-ready app where users can:
1. Sign up and choose a plan
2. Create newsletters and/or podcasts
3. Distribute to email and Spotify
4. Pay for what they use
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, HTTPException, Request, Form, BackgroundTasks, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv(override=True)

# In-memory storage for pending generations (sessions are in Supabase)
pending_generations = {}  # Store generation requests until payment completes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle."""
    yield


def create_app(output_dir: str = "./output") -> FastAPI:
    """Create the main application."""

    app = FastAPI(
        title="PodcastOS",
        description="Turn your ideas into newsletters and podcasts",
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

    # Mount static files
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(output_path)), name="files")

    return app


app = create_app()


# ============== PRICING ==============
PRICING = {
    "newsletter": {
        "name": "Newsletter Only",
        "price": 29,
        "features": ["Written newsletter", "Email-ready HTML", "Markdown export"],
        "outputs": ["newsletter"],
    },
    "podcast": {
        "name": "Podcast Only",
        "price": 49,
        "features": ["Audio podcast", "RSS feed for Spotify", "Episode segments"],
        "outputs": ["podcast"],
    },
    "bundle": {
        "name": "Newsletter + Podcast",
        "price": 69,
        "features": ["Written newsletter", "Audio podcast", "Both formats from one source", "Save 15%"],
        "outputs": ["newsletter", "podcast"],
    },
}


# ============== HTML PAGES ==============

LANDING_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PodcastOS - Turn Ideas into Content</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg: #0a0a0f;
            --card: #12121a;
            --border: rgba(255,255,255,0.1);
            --cyan: #00d4ff;
            --purple: #7b2cbf;
            --green: #00ff88;
            --text: #ffffff;
            --text-dim: #888;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }

        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }

        /* Header */
        header {
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
        }

        nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, var(--cyan), var(--purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .nav-links a {
            color: var(--text-dim);
            text-decoration: none;
            margin-left: 30px;
            transition: color 0.2s;
        }

        .nav-links a:hover { color: var(--text); }

        .btn {
            display: inline-block;
            padding: 12px 28px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
            font-size: 1rem;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(0, 212, 255, 0.3);
        }

        .btn-secondary {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text);
        }

        /* Hero */
        .hero {
            text-align: center;
            padding: 100px 0 80px;
        }

        .hero h1 {
            font-size: 3.5rem;
            margin-bottom: 20px;
            line-height: 1.2;
        }

        .hero h1 span {
            background: linear-gradient(90deg, var(--cyan), var(--purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            font-size: 1.3rem;
            color: var(--text-dim);
            max-width: 600px;
            margin: 0 auto 40px;
        }

        .hero-cta { display: flex; gap: 15px; justify-content: center; }

        /* How it works */
        .how-it-works {
            padding: 80px 0;
            background: var(--card);
        }

        .section-title {
            text-align: center;
            font-size: 2rem;
            margin-bottom: 50px;
        }

        .steps {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 40px;
        }

        .step {
            text-align: center;
            padding: 30px;
        }

        .step-icon {
            font-size: 3rem;
            margin-bottom: 20px;
        }

        .step h3 {
            font-size: 1.3rem;
            margin-bottom: 10px;
        }

        .step p { color: var(--text-dim); }

        /* Pricing */
        .pricing {
            padding: 80px 0;
        }

        .pricing-cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 30px;
            margin-top: 50px;
        }

        .pricing-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 40px 30px;
            text-align: center;
            position: relative;
            transition: all 0.3s;
        }

        .pricing-card:hover {
            transform: translateY(-5px);
            border-color: var(--cyan);
        }

        .pricing-card.featured {
            border-color: var(--purple);
            background: linear-gradient(180deg, rgba(123, 44, 191, 0.1), transparent);
        }

        .pricing-card.featured::before {
            content: 'BEST VALUE';
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--purple);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .plan-name {
            font-size: 1.2rem;
            color: var(--text-dim);
            margin-bottom: 10px;
        }

        .plan-price {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .plan-price span {
            font-size: 1rem;
            color: var(--text-dim);
        }

        .plan-features {
            list-style: none;
            margin: 30px 0;
            text-align: left;
        }

        .plan-features li {
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .plan-features li::before {
            content: '✓';
            color: var(--green);
        }

        /* Footer */
        footer {
            padding: 40px 0;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-dim);
        }

        @media (max-width: 768px) {
            .hero h1 { font-size: 2.5rem; }
            .steps, .pricing-cards { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header>
        <nav class="container">
            <div class="logo">🎙️ PodcastOS</div>
            <div class="nav-links">
                <a href="#pricing">Pricing</a>
                <a href="#how">How it works</a>
                <a href="/app" class="btn btn-primary">Get Started</a>
            </div>
        </nav>
    </header>

    <section class="hero">
        <div class="container">
            <h1>Turn your ideas into<br><span>newsletters & podcasts</span></h1>
            <p>Enter a topic. Get a professional newsletter AND podcast in minutes. No writing, recording, or editing required.</p>
            <div class="hero-cta">
                <a href="/app" class="btn btn-primary">Start Creating →</a>
                <a href="#how" class="btn btn-secondary">See how it works</a>
            </div>
        </div>
    </section>

    <section class="how-it-works" id="how">
        <div class="container">
            <h2 class="section-title">How It Works</h2>
            <div class="steps">
                <div class="step">
                    <div class="step-icon">💡</div>
                    <h3>1. Enter Your Topic</h3>
                    <p>Tell us what you want to cover. A trend, a news story, or paste your own content.</p>
                </div>
                <div class="step">
                    <div class="step-icon">🔬</div>
                    <h3>2. We Research & Write</h3>
                    <p>AI researches your topic, finds facts and expert opinions, creates professional content.</p>
                </div>
                <div class="step">
                    <div class="step-icon">🚀</div>
                    <h3>3. Get Newsletter + Podcast</h3>
                    <p>Download your email-ready newsletter AND listen to your podcast. Publish anywhere.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="pricing" id="pricing">
        <div class="container">
            <h2 class="section-title">Simple Pricing</h2>
            <p style="text-align: center; color: var(--text-dim); margin-top: -30px;">Pay per generation. No subscriptions required.</p>

            <div class="pricing-cards">
                <div class="pricing-card">
                    <div class="plan-name">Newsletter Only</div>
                    <div class="plan-price">$29 <span>/generation</span></div>
                    <ul class="plan-features">
                        <li>AI-researched content</li>
                        <li>Email-ready HTML</li>
                        <li>Markdown export</li>
                        <li>~800 words</li>
                    </ul>
                    <a href="/app?plan=newsletter" class="btn btn-secondary" style="width: 100%;">Choose Newsletter</a>
                </div>

                <div class="pricing-card featured">
                    <div class="plan-name">Newsletter + Podcast</div>
                    <div class="plan-price">$69 <span>/generation</span></div>
                    <ul class="plan-features">
                        <li>Everything in Newsletter</li>
                        <li>Professional podcast audio</li>
                        <li>RSS feed for Spotify</li>
                        <li>~6 minute episode</li>
                        <li>Save $9 vs separate</li>
                    </ul>
                    <a href="/app?plan=bundle" class="btn btn-primary" style="width: 100%;">Choose Bundle</a>
                </div>

                <div class="pricing-card">
                    <div class="plan-name">Podcast Only</div>
                    <div class="plan-price">$49 <span>/generation</span></div>
                    <ul class="plan-features">
                        <li>AI-researched script</li>
                        <li>Human-like audio</li>
                        <li>RSS feed for Spotify</li>
                        <li>~6 minute episode</li>
                    </ul>
                    <a href="/app?plan=podcast" class="btn btn-secondary" style="width: 100%;">Choose Podcast</a>
                </div>
            </div>
        </div>
    </section>

    <footer>
        <div class="container">
            <p>© 2025 PodcastOS. AI-powered content creation.</p>
        </div>
    </footer>
</body>
</html>
"""

APP_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Create Content - PodcastOS</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg: #0a0a0f;
            --card: #12121a;
            --border: rgba(255,255,255,0.1);
            --cyan: #00d4ff;
            --purple: #7b2cbf;
            --green: #00ff88;
            --text: #ffffff;
            --text-dim: #888;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .container { max-width: 800px; margin: 0 auto; padding: 40px 20px; }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, var(--cyan), var(--purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-decoration: none;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
        }

        h1 {
            font-size: 1.8rem;
            margin-bottom: 10px;
        }

        .subtitle {
            color: var(--text-dim);
            margin-bottom: 30px;
        }

        .form-group {
            margin-bottom: 25px;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }

        input, textarea, select {
            width: 100%;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: var(--bg);
            color: var(--text);
            font-size: 1rem;
            font-family: inherit;
        }

        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: var(--cyan);
        }

        textarea { min-height: 150px; resize: vertical; }

        .plan-selector {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }

        .plan-option {
            background: var(--bg);
            border: 2px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }

        .plan-option:hover {
            border-color: var(--cyan);
        }

        .plan-option.selected {
            border-color: var(--cyan);
            background: rgba(0, 212, 255, 0.1);
        }

        .plan-option input { display: none; }

        .plan-option .plan-name {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .plan-option .plan-price {
            color: var(--cyan);
            font-size: 1.3rem;
            font-weight: 700;
        }

        .btn {
            display: inline-block;
            padding: 15px 40px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
            width: 100%;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(0, 212, 255, 0.3);
        }

        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .or-divider {
            text-align: center;
            color: var(--text-dim);
            margin: 20px 0;
            position: relative;
        }

        .or-divider::before, .or-divider::after {
            content: '';
            position: absolute;
            top: 50%;
            width: 45%;
            height: 1px;
            background: var(--border);
        }

        .or-divider::before { left: 0; }
        .or-divider::after { right: 0; }

        /* Results */
        .results {
            display: none;
        }

        .results.show {
            display: block;
        }

        .result-card {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
        }

        .result-card h3 {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }

        .result-card .icon {
            font-size: 1.5rem;
        }

        .result-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }

        .result-actions a, .result-actions button {
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 0.9rem;
            cursor: pointer;
        }

        .btn-download {
            background: var(--cyan);
            color: var(--bg);
            border: none;
        }

        .btn-preview {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text);
        }

        /* Progress */
        .progress-container {
            display: none;
            text-align: center;
            padding: 40px;
        }

        .progress-container.show {
            display: block;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 3px solid var(--border);
            border-top-color: var(--cyan);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        .progress-text {
            color: var(--text-dim);
        }

        .progress-step {
            margin-top: 10px;
            color: var(--cyan);
        }

        /* Audio player */
        audio {
            width: 100%;
            margin-top: 15px;
        }

        .newsletter-preview {
            background: white;
            color: #333;
            padding: 30px;
            border-radius: 10px;
            max-height: 400px;
            overflow-y: auto;
            margin-top: 15px;
        }

        @media (max-width: 768px) {
            .plan-selector { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <a href="/" class="logo">🎙️ PodcastOS</a>
        </header>

        <!-- Creation Form -->
        <div class="card" id="creation-form">
            <h1>Create Your Content</h1>
            <p class="subtitle">Enter a topic or paste your own content. We'll create a professional newsletter and/or podcast.</p>

            <form id="content-form">
                <!-- Plan Selection -->
                <label>What do you want to create?</label>
                <div class="plan-selector">
                    <label class="plan-option" data-plan="newsletter">
                        <input type="radio" name="plan" value="newsletter">
                        <div class="plan-name">📧 Newsletter</div>
                        <div class="plan-price">$29</div>
                    </label>
                    <label class="plan-option selected" data-plan="bundle">
                        <input type="radio" name="plan" value="bundle" checked>
                        <div class="plan-name">📧 + 🎙️ Both</div>
                        <div class="plan-price">$69</div>
                    </label>
                    <label class="plan-option" data-plan="podcast">
                        <input type="radio" name="plan" value="podcast">
                        <div class="plan-name">🎙️ Podcast</div>
                        <div class="plan-price">$49</div>
                    </label>
                </div>

                <div class="form-group">
                    <label for="brand_name">Your Brand Name</label>
                    <input type="text" id="brand_name" name="brand_name" placeholder="e.g., Tech Weekly, The Morning Brew" value="Tech Daily" required>
                </div>

                <div class="form-group">
                    <label for="topic">Topic to Cover</label>
                    <input type="text" id="topic" name="topic" placeholder="e.g., AI trends in 2025, Latest tech news, Startup funding updates">
                </div>

                <div class="or-divider">OR</div>

                <div class="form-group">
                    <label for="user_content">Paste Your Own Content (optional)</label>
                    <textarea id="user_content" name="user_content" placeholder="Paste your blog post, notes, or article here. We'll enhance it with research and convert to newsletter/podcast format."></textarea>
                </div>

                <button type="submit" class="btn btn-primary">
                    Generate Content →
                </button>
            </form>
        </div>

        <!-- Progress -->
        <div class="card progress-container" id="progress">
            <div class="spinner"></div>
            <div class="progress-text">Generating your content...</div>
            <div class="progress-step" id="progress-step">Researching topic...</div>
        </div>

        <!-- Results -->
        <div class="results" id="results">
            <div class="card">
                <h1>✨ Your Content is Ready!</h1>
                <p class="subtitle" id="result-summary">Generated newsletter and podcast for "AI Trends 2025"</p>
            </div>

            <div class="result-card" id="newsletter-result" style="display: none;">
                <h3><span class="icon">📧</span> Newsletter</h3>
                <p id="newsletter-stats">800 words · 4 min read</p>
                <div class="result-actions">
                    <a href="#" class="btn-download" id="download-html">Download HTML</a>
                    <a href="#" class="btn-download" id="download-md">Download Markdown</a>
                    <button class="btn-preview" onclick="togglePreview()">Preview</button>
                </div>
                <div class="newsletter-preview" id="newsletter-preview" style="display: none;"></div>
            </div>

            <div class="result-card" id="podcast-result" style="display: none;">
                <h3><span class="icon">🎙️</span> Podcast</h3>
                <p id="podcast-stats">6:30 duration · 5 segments</p>
                <div class="result-actions">
                    <a href="#" class="btn-download" id="download-audio">Download MP3</a>
                    <a href="#" class="btn-download" id="download-rss">Get RSS Feed</a>
                </div>
                <audio controls id="audio-player"></audio>
            </div>

            <div class="card" style="text-align: center;">
                <button class="btn btn-primary" onclick="createAnother()">Create Another →</button>
            </div>
        </div>
    </div>

    <script>
        // Plan selection
        document.querySelectorAll('.plan-option').forEach(option => {
            option.addEventListener('click', () => {
                document.querySelectorAll('.plan-option').forEach(o => o.classList.remove('selected'));
                option.classList.add('selected');
                option.querySelector('input').checked = true;
            });
        });

        // Form submission - goes through checkout
        document.getElementById('content-form').addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const data = {
                plan: formData.get('plan'),
                brand_name: formData.get('brand_name'),
                topic: formData.get('topic'),
                user_content: formData.get('user_content'),
            };

            // Show progress
            document.getElementById('creation-form').style.display = 'none';
            document.getElementById('progress').classList.add('show');
            document.getElementById('progress-step').textContent = 'Processing...';

            try {
                // First, create checkout session
                const checkoutResponse = await fetch('/api/checkout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });

                const checkoutResult = await checkoutResponse.json();

                if (checkoutResult.checkout_url) {
                    // Redirect to Stripe checkout
                    window.location.href = checkoutResult.checkout_url;
                } else if (checkoutResult.demo_mode) {
                    // Demo mode - generate directly without payment
                    document.getElementById('progress-step').textContent = 'Demo mode - generating content...';

                    const steps = [
                        'Researching topic...',
                        'Finding key facts and opinions...',
                        'Generating newsletter content...',
                        'Creating podcast script...',
                        'Generating audio...',
                        'Finalizing...'
                    ];

                    let stepIndex = 0;
                    const stepInterval = setInterval(() => {
                        if (stepIndex < steps.length) {
                            document.getElementById('progress-step').textContent = steps[stepIndex];
                            stepIndex++;
                        }
                    }, 3000);

                    // Generate directly in demo mode
                    const genResponse = await fetch(checkoutResult.redirect || `/api/generate-demo?plan=${data.plan}&brand_name=${encodeURIComponent(data.brand_name)}&topic=${encodeURIComponent(data.topic || '')}`);
                    const result = await genResponse.json();

                    clearInterval(stepInterval);

                    if (result.success) {
                        localStorage.setItem('lastResult', JSON.stringify(result));
                        window.location.href = '/results?id=' + result.id;
                    } else {
                        alert('Generation failed: ' + (result.error || 'Unknown error'));
                        location.reload();
                    }
                } else {
                    alert('Error: ' + (checkoutResult.error || 'Unknown error'));
                    location.reload();
                }
            } catch (error) {
                alert('Error: ' + error.message);
                location.reload();
            }
        });

        function showResults(result, input) {
            document.getElementById('progress').classList.remove('show');
            document.getElementById('results').classList.add('show');

            document.getElementById('result-summary').textContent =
                `Generated content for "${input.topic || input.brand_name}"`;

            // Newsletter results
            if (result.newsletter_html_path) {
                document.getElementById('newsletter-result').style.display = 'block';
                document.getElementById('newsletter-stats').textContent =
                    `${result.word_count || 800} words · ${Math.ceil((result.word_count || 800) / 200)} min read`;
                document.getElementById('download-html').href = '/files/' + result.newsletter_html_path.split('/').pop();
                document.getElementById('download-md').href = '/files/' + result.newsletter_markdown_path.split('/').pop();

                // Load preview
                fetch('/files/' + result.newsletter_html_path.split('/').pop())
                    .then(r => r.text())
                    .then(html => {
                        document.getElementById('newsletter-preview').innerHTML = html;
                    });
            }

            // Podcast results
            if (result.podcast_audio_path) {
                document.getElementById('podcast-result').style.display = 'block';
                const duration = Math.floor(result.audio_duration_seconds / 60);
                const secs = Math.floor(result.audio_duration_seconds % 60);
                document.getElementById('podcast-stats').textContent =
                    `${duration}:${secs.toString().padStart(2, '0')} duration`;
                document.getElementById('download-audio').href = '/files/' + result.podcast_audio_path.split('/').pop();
                document.getElementById('audio-player').src = '/files/' + result.podcast_audio_path.split('/').pop();
            }
        }

        function togglePreview() {
            const preview = document.getElementById('newsletter-preview');
            preview.style.display = preview.style.display === 'none' ? 'block' : 'none';
        }

        function createAnother() {
            document.getElementById('results').classList.remove('show');
            document.getElementById('creation-form').style.display = 'block';
            document.getElementById('content-form').reset();
            document.querySelectorAll('.plan-option').forEach(o => o.classList.remove('selected'));
            document.querySelector('.plan-option[data-plan="bundle"]').classList.add('selected');
        }

        // Check URL for plan parameter
        const urlParams = new URLSearchParams(window.location.search);
        const plan = urlParams.get('plan');
        if (plan) {
            document.querySelectorAll('.plan-option').forEach(o => o.classList.remove('selected'));
            const option = document.querySelector(`.plan-option[data-plan="${plan}"]`);
            if (option) {
                option.classList.add('selected');
                option.querySelector('input').checked = true;
            }
        }
    </script>
</body>
</html>
"""


# ============== API ROUTES ==============

@app.get("/", response_class=HTMLResponse)
async def landing():
    """Landing page."""
    return LANDING_PAGE


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    """Main app page."""
    return APP_PAGE


class GenerateRequest(BaseModel):
    plan: str = "bundle"
    brand_name: str = "Tech Daily"
    topic: Optional[str] = None
    user_content: Optional[str] = None


@app.post("/api/generate")
async def generate_content(request: GenerateRequest):
    """Generate newsletter and/or podcast."""
    from src.intelligence.synthesis.content_engine import ContentEngine, ContentInput

    try:
        engine = ContentEngine(output_dir="./output")

        # Determine what to generate based on plan
        generate_newsletter = request.plan in ["newsletter", "bundle"]
        generate_podcast = request.plan in ["podcast", "bundle"]

        input_data = ContentInput(
            topic=request.topic or "Today's Tech News",
            user_content=request.user_content if request.user_content else None,
            brand_name=request.brand_name,
            generate_newsletter=generate_newsletter,
            generate_podcast=generate_podcast,
        )

        result = await engine.generate(input_data)

        return {
            "success": result.success,
            "id": result.id,
            "topic": result.topic,
            "word_count": result.word_count,
            "audio_duration_seconds": result.audio_duration_seconds,
            "newsletter_html_path": result.newsletter_html_path,
            "newsletter_markdown_path": result.newsletter_markdown_path,
            "podcast_audio_path": result.podcast_audio_path,
            "errors": result.errors,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@app.get("/api/pricing")
async def get_pricing():
    """Get pricing information."""
    return PRICING


@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


# ============== AUTHENTICATION ==============

from .auth import AuthService, SignUpRequest, LoginRequest, AuthUser, get_current_user, require_auth


@app.post("/api/auth/signup")
async def signup(request: SignUpRequest):
    """Sign up a new user."""
    auth_service = AuthService()
    result = await auth_service.sign_up(request)

    if result.success:
        return {
            "success": True,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "full_name": result.user.full_name,
            },
            "access_token": result.user.access_token,
            "refresh_token": result.user.refresh_token,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error)


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Log in an existing user."""
    auth_service = AuthService()
    result = await auth_service.login(request)

    if result.success:
        return {
            "success": True,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "full_name": result.user.full_name,
            },
            "access_token": result.user.access_token,
            "refresh_token": result.user.refresh_token,
        }
    else:
        raise HTTPException(status_code=401, detail=result.error)


@app.post("/api/auth/logout")
async def logout(user: AuthUser = Depends(get_current_user)):
    """Log out current user."""
    if user:
        auth_service = AuthService()
        await auth_service.logout(user.access_token)
    return {"success": True}


@app.get("/api/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    """Get current authenticated user."""
    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        }
    }


@app.post("/api/auth/reset-password")
async def reset_password(email: str):
    """Send password reset email."""
    auth_service = AuthService()
    success = await auth_service.reset_password(email)

    if success:
        return {"success": True, "message": "Password reset email sent"}
    else:
        raise HTTPException(status_code=400, detail="Failed to send reset email")


# ============== STRIPE BILLING ==============

class CreateCheckoutRequest(BaseModel):
    plan: str = "bundle"
    brand_name: str = "Tech Daily"
    topic: Optional[str] = None
    user_content: Optional[str] = None


@app.post("/api/checkout")
async def create_checkout(request: CreateCheckoutRequest):
    """Create Stripe checkout session."""
    import uuid

    # Check if Stripe is configured
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        # Demo mode - skip payment, generate directly
        return {
            "demo_mode": True,
            "message": "Stripe not configured - generating in demo mode",
            "redirect": f"/api/generate-demo?plan={request.plan}&brand_name={request.brand_name}&topic={request.topic or ''}"
        }

    try:
        from .billing import create_checkout_session

        # Generate unique ID for this generation request
        generation_id = str(uuid.uuid4())[:8]

        # Store the generation request
        pending_generations[generation_id] = {
            "plan": request.plan,
            "brand_name": request.brand_name,
            "topic": request.topic,
            "user_content": request.user_content,
        }

        # Create Stripe checkout
        base_url = os.getenv("BASE_URL", "http://127.0.0.1:8080")
        session = create_checkout_session(
            plan=request.plan,
            success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}&gen_id={generation_id}",
            cancel_url=f"{base_url}/app?cancelled=true",
            metadata={
                "plan": request.plan,
                "generation_id": generation_id,
            }
        )

        return {
            "checkout_url": session.checkout_url,
            "session_id": session.session_id,
        }

    except Exception as e:
        return {
            "error": str(e),
            "demo_mode": True,
            "message": "Stripe error - generating in demo mode",
        }


@app.get("/success", response_class=HTMLResponse)
async def payment_success(session_id: str = None, gen_id: str = None):
    """Handle successful payment - generate content."""

    # Return a page that will trigger generation
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Successful - PodcastOS</title>
        <style>
            body {{
                font-family: -apple-system, sans-serif;
                background: #0a0a0f;
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                padding: 40px;
            }}
            .spinner {{
                width: 50px;
                height: 50px;
                border: 3px solid rgba(255,255,255,0.1);
                border-top-color: #00d4ff;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px;
            }}
            @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
            h1 {{ color: #00ff88; margin-bottom: 10px; }}
            p {{ color: #888; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✓ Payment Successful!</h1>
            <div class="spinner"></div>
            <p id="status">Generating your content...</p>
        </div>
        <script>
            async function generateContent() {{
                try {{
                    const response = await fetch('/api/generate-paid?gen_id={gen_id}&session_id={session_id}');
                    const result = await response.json();

                    if (result.success) {{
                        // Redirect to results page with data
                        localStorage.setItem('lastResult', JSON.stringify(result));
                        window.location.href = '/results?id=' + result.id;
                    }} else {{
                        document.getElementById('status').textContent = 'Error: ' + (result.error || 'Generation failed');
                    }}
                }} catch (error) {{
                    document.getElementById('status').textContent = 'Error: ' + error.message;
                }}
            }}
            generateContent();
        </script>
    </body>
    </html>
    """


@app.get("/api/generate-paid")
async def generate_after_payment(gen_id: str, session_id: str = None):
    """Generate content after successful payment."""

    # Verify payment if Stripe is configured
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if stripe_key and session_id:
        from .billing import verify_payment
        verification = verify_payment(session_id)
        if not verification.paid:
            return {"success": False, "error": "Payment not verified"}

    # Get stored generation request
    gen_request = pending_generations.get(gen_id)
    if not gen_request:
        return {"success": False, "error": "Generation request not found"}

    # Generate content
    from src.intelligence.synthesis.content_engine import ContentEngine, ContentInput

    try:
        engine = ContentEngine(output_dir="./output")

        generate_newsletter = gen_request["plan"] in ["newsletter", "bundle"]
        generate_podcast = gen_request["plan"] in ["podcast", "bundle"]

        input_data = ContentInput(
            topic=gen_request.get("topic") or "Today's Tech News",
            user_content=gen_request.get("user_content"),
            brand_name=gen_request.get("brand_name", "Tech Daily"),
            generate_newsletter=generate_newsletter,
            generate_podcast=generate_podcast,
        )

        result = await engine.generate(input_data)

        # Clean up pending request
        del pending_generations[gen_id]

        return {
            "success": result.success,
            "id": result.id,
            "topic": result.topic,
            "word_count": result.word_count,
            "audio_duration_seconds": result.audio_duration_seconds,
            "newsletter_html_path": result.newsletter_html_path,
            "newsletter_markdown_path": result.newsletter_markdown_path,
            "podcast_audio_path": result.podcast_audio_path,
            "errors": result.errors,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/generate-demo")
async def generate_demo(plan: str = "bundle", brand_name: str = "Tech Daily", topic: str = ""):
    """Generate content in demo mode (no payment)."""
    from src.intelligence.synthesis.content_engine import ContentEngine, ContentInput

    try:
        engine = ContentEngine(output_dir="./output")

        generate_newsletter = plan in ["newsletter", "bundle"]
        generate_podcast = plan in ["podcast", "bundle"]

        input_data = ContentInput(
            topic=topic or "Today's Tech News",
            brand_name=brand_name,
            generate_newsletter=generate_newsletter,
            generate_podcast=generate_podcast,
        )

        result = await engine.generate(input_data)

        return {
            "success": result.success,
            "id": result.id,
            "topic": result.topic,
            "word_count": result.word_count,
            "audio_duration_seconds": result.audio_duration_seconds,
            "newsletter_html_path": result.newsletter_html_path,
            "newsletter_markdown_path": result.newsletter_markdown_path,
            "podcast_audio_path": result.podcast_audio_path,
            "errors": result.errors,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============== EMAIL DELIVERY ==============

class SendEmailRequest(BaseModel):
    newsletter_html_path: str
    subject: str
    recipients: list[str]
    from_name: str = "PodcastOS"


@app.post("/api/send-newsletter")
async def send_newsletter(request: SendEmailRequest):
    """Send newsletter via email."""
    from .email_service import EmailService

    try:
        # Read the newsletter HTML
        with open(request.newsletter_html_path, "r") as f:
            html_content = f.read()

        service = EmailService()
        result = await service.send_newsletter(
            newsletter_html=html_content,
            subject=request.subject,
            recipients=request.recipients,
            from_name=request.from_name,
        )

        return {
            "success": result.success,
            "message_id": result.message_id,
            "recipients_count": result.recipients_count,
            "error": result.error,
            "provider": service.provider,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/email-provider")
async def get_email_provider():
    """Get current email provider status."""
    from .email_service import EmailService

    service = EmailService()
    return {
        "provider": service.provider,
        "configured": service.provider != "local",
    }


# ============== SUBSCRIBER MANAGEMENT ==============

class SubscriberRequest(BaseModel):
    email: str
    name: Optional[str] = None


@app.post("/api/subscribers/add")
async def add_subscriber(request: SubscriberRequest):
    """Add a subscriber to the list."""
    from .email_service import SubscriberList

    subscribers = SubscriberList()
    added = subscribers.add(request.email, request.name)

    return {
        "success": added,
        "message": "Subscriber added" if added else "Already subscribed",
        "total_subscribers": subscribers.count(),
    }


@app.post("/api/subscribers/remove")
async def remove_subscriber(request: SubscriberRequest):
    """Remove a subscriber from the list."""
    from .email_service import SubscriberList

    subscribers = SubscriberList()
    removed = subscribers.remove(request.email)

    return {
        "success": removed,
        "message": "Subscriber removed" if removed else "Not found",
        "total_subscribers": subscribers.count(),
    }


@app.get("/api/subscribers")
async def list_subscribers():
    """List all subscribers."""
    from .email_service import SubscriberList

    subscribers = SubscriberList()

    return {
        "subscribers": subscribers.list_all(),
        "count": subscribers.count(),
    }


# ============== RSS FEED FOR SPOTIFY ==============

class CreateFeedRequest(BaseModel):
    title: str
    description: str
    author: str = "PodcastOS"


class AddEpisodeRequest(BaseModel):
    feed_id: str
    audio_path: str
    title: str
    description: str
    duration_seconds: int


@app.post("/api/rss/create")
async def create_rss_feed(request: CreateFeedRequest):
    """Create a new podcast RSS feed."""
    from .rss_feed import RSSFeedGenerator, PodcastChannel

    try:
        generator = RSSFeedGenerator()
        channel = PodcastChannel(
            title=request.title,
            description=request.description,
            author=request.author,
        )
        feed_id = generator.create_feed(channel)

        return {
            "success": True,
            "feed_id": feed_id,
            "rss_url": generator.get_rss_url(feed_id),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/rss/add-episode")
async def add_rss_episode(request: AddEpisodeRequest):
    """Add an episode to an RSS feed."""
    from .rss_feed import RSSFeedGenerator

    try:
        generator = RSSFeedGenerator()
        episode = generator.add_episode_from_generation(
            feed_id=request.feed_id,
            audio_path=request.audio_path,
            title=request.title,
            description=request.description,
            duration_seconds=request.duration_seconds,
        )

        if episode:
            return {
                "success": True,
                "episode_id": episode.id,
                "rss_url": generator.get_rss_url(request.feed_id),
            }
        else:
            return {"success": False, "error": "Feed not found or audio file missing"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/rss/feeds")
async def list_rss_feeds():
    """List all RSS feeds."""
    from .rss_feed import RSSFeedGenerator

    generator = RSSFeedGenerator()
    feeds = generator.list_feeds()

    return {
        "feeds": [
            {
                "id": f["id"],
                "title": f["channel"]["title"],
                "episode_count": len(f["episodes"]),
                "rss_url": generator.get_rss_url(f["id"]),
            }
            for f in feeds
        ],
        "count": len(feeds),
    }


@app.get("/api/rss/{feed_id}")
async def get_rss_feed(feed_id: str):
    """Get a specific RSS feed details."""
    from .rss_feed import RSSFeedGenerator

    generator = RSSFeedGenerator()
    feed = generator.get_feed(feed_id)

    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    return {
        "id": feed_id,
        "channel": feed["channel"],
        "episodes": feed["episodes"],
        "rss_url": generator.get_rss_url(feed_id),
    }


@app.get("/rss/{feed_id}.xml")
async def serve_rss_xml(feed_id: str):
    """Serve the RSS XML file for podcast apps."""
    from fastapi.responses import Response
    from .rss_feed import RSSFeedGenerator

    generator = RSSFeedGenerator()
    xml_content = generator.get_rss_xml(feed_id)

    if not xml_content:
        raise HTTPException(status_code=404, detail="Feed not found")

    return Response(
        content=xml_content,
        media_type="application/rss+xml",
        headers={
            "Content-Disposition": f"inline; filename={feed_id}.xml"
        }
    )


@app.get("/results", response_class=HTMLResponse)
async def results_page(id: str = ""):
    """Results page showing generated content."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Your Content - PodcastOS</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, sans-serif;
                background: #0a0a0f;
                color: white;
                min-height: 100vh;
                padding: 40px 20px;
            }
            .container { max-width: 800px; margin: 0 auto; }
            .card {
                background: #12121a;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 16px;
                padding: 30px;
                margin-bottom: 20px;
            }
            h1 { margin-bottom: 10px; }
            .subtitle { color: #888; margin-bottom: 30px; }
            h3 { margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
            h4 { margin: 20px 0 10px; color: #00d4ff; }
            .icon { font-size: 1.5rem; }
            .stats { color: #888; margin-bottom: 15px; }
            .actions { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 15px; }
            .btn {
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 500;
                cursor: pointer;
                border: none;
                font-size: 0.95rem;
            }
            .btn-primary {
                background: linear-gradient(135deg, #00d4ff, #7b2cbf);
                color: white;
            }
            .btn-secondary {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.2);
                color: white;
            }
            .btn-success {
                background: #00ff88;
                color: #0a0a0f;
            }
            .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            audio { width: 100%; margin-top: 15px; }
            .preview {
                background: white;
                color: #333;
                padding: 20px;
                border-radius: 10px;
                margin-top: 15px;
                max-height: 300px;
                overflow-y: auto;
                display: none;
            }
            .logo {
                font-size: 1.5rem;
                font-weight: 700;
                background: linear-gradient(90deg, #00d4ff, #7b2cbf);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-decoration: none;
                display: block;
                margin-bottom: 30px;
            }
            .distribute-section {
                border-top: 1px solid rgba(255,255,255,0.1);
                padding-top: 20px;
                margin-top: 20px;
            }
            .email-form {
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }
            .email-form input {
                flex: 1;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.2);
                background: #0a0a0f;
                color: white;
            }
            .rss-url {
                background: #0a0a0f;
                padding: 12px;
                border-radius: 8px;
                font-family: monospace;
                font-size: 0.9rem;
                word-break: break-all;
                margin-top: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .rss-url input {
                flex: 1;
                background: transparent;
                border: none;
                color: #00d4ff;
                font-family: monospace;
            }
            .status-message {
                padding: 10px;
                border-radius: 8px;
                margin-top: 10px;
                display: none;
            }
            .status-message.success {
                background: rgba(0, 255, 136, 0.2);
                color: #00ff88;
                display: block;
            }
            .status-message.error {
                background: rgba(255, 100, 100, 0.2);
                color: #ff6464;
                display: block;
            }
            .provider-badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                background: rgba(0, 212, 255, 0.2);
                color: #00d4ff;
                font-size: 0.8rem;
                margin-left: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="logo">🎙️ PodcastOS</a>

            <div class="card">
                <h1>✨ Your Content is Ready!</h1>
                <p class="subtitle" id="summary">Loading...</p>
            </div>

            <div class="card" id="newsletter-card" style="display: none;">
                <h3><span class="icon">📧</span> Newsletter</h3>
                <p class="stats" id="newsletter-stats"></p>
                <div class="actions">
                    <a href="#" class="btn btn-primary" id="download-html">Download HTML</a>
                    <a href="#" class="btn btn-secondary" id="download-md">Download Markdown</a>
                    <button class="btn btn-secondary" onclick="togglePreview()">Preview</button>
                    <button class="btn btn-secondary" onclick="openEditor()" style="background: linear-gradient(135deg, #7b2cbf, #00d4ff); border: none;">✏️ Edit in Studio</button>
                </div>
                <div class="preview" id="preview"></div>

                <div class="distribute-section">
                    <h4>Send via Email <span class="provider-badge" id="email-provider">checking...</span></h4>
                    <p style="color: #888; font-size: 0.9rem; margin-bottom: 10px;">
                        Send this newsletter to your subscribers
                    </p>
                    <div class="email-form">
                        <input type="email" id="recipient-email" placeholder="Enter email address (or comma-separated list)">
                        <button class="btn btn-success" onclick="sendNewsletter()">Send</button>
                    </div>
                    <div class="status-message" id="email-status"></div>
                </div>
            </div>

            <div class="card" id="podcast-card" style="display: none;">
                <h3><span class="icon">🎙️</span> Podcast</h3>
                <p class="stats" id="podcast-stats"></p>
                <div class="actions">
                    <a href="#" class="btn btn-primary" id="download-audio">Download Audio</a>
                </div>
                <audio controls id="audio-player"></audio>

                <div class="distribute-section">
                    <h4>Publish to Spotify & Apple Podcasts</h4>
                    <p style="color: #888; font-size: 0.9rem; margin-bottom: 10px;">
                        Create an RSS feed to submit to podcast platforms
                    </p>
                    <div id="rss-create-section">
                        <div class="email-form">
                            <input type="text" id="podcast-title" placeholder="Podcast show name" value="">
                            <button class="btn btn-success" onclick="createRSSFeed()">Create RSS Feed</button>
                        </div>
                    </div>
                    <div id="rss-result-section" style="display: none;">
                        <p style="color: #00ff88; margin-bottom: 10px;">RSS feed created! Submit this URL to podcast platforms:</p>
                        <div class="rss-url">
                            <input type="text" id="rss-url" readonly>
                            <button class="btn btn-secondary" onclick="copyRSSUrl()" style="padding: 8px 16px;">Copy</button>
                        </div>
                        <p style="color: #888; font-size: 0.85rem; margin-top: 15px;">
                            Submit your RSS feed:<br>
                            • <a href="https://podcasters.spotify.com" target="_blank" style="color: #00d4ff;">Spotify for Podcasters</a><br>
                            • <a href="https://podcastsconnect.apple.com" target="_blank" style="color: #00d4ff;">Apple Podcasts Connect</a><br>
                            • <a href="https://podcasts.google.com/publish" target="_blank" style="color: #00d4ff;">Google Podcasts</a>
                        </p>
                    </div>
                    <div class="status-message" id="rss-status"></div>
                </div>
            </div>

            <div class="card" style="text-align: center;">
                <a href="/app" class="btn btn-primary">Create Another →</a>
            </div>
        </div>

        <script>
            const result = JSON.parse(localStorage.getItem('lastResult') || '{}');

            if (result.topic) {
                document.getElementById('summary').textContent = 'Generated content for "' + result.topic + '"';
                document.getElementById('podcast-title').value = result.topic;
            }

            if (result.newsletter_html_path) {
                document.getElementById('newsletter-card').style.display = 'block';
                document.getElementById('newsletter-stats').textContent =
                    (result.word_count || 800) + ' words · ' + Math.ceil((result.word_count || 800) / 200) + ' min read';

                const htmlFile = result.newsletter_html_path.split('/').pop();
                const mdFile = result.newsletter_markdown_path.split('/').pop();
                document.getElementById('download-html').href = '/files/' + htmlFile;
                document.getElementById('download-md').href = '/files/' + mdFile;

                fetch('/files/' + htmlFile)
                    .then(r => r.text())
                    .then(html => document.getElementById('preview').innerHTML = html);

                // Check email provider
                fetch('/api/email-provider')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('email-provider').textContent = data.provider;
                        if (data.provider === 'local') {
                            document.getElementById('email-provider').textContent = 'demo mode';
                        }
                    });
            }

            if (result.podcast_audio_path) {
                document.getElementById('podcast-card').style.display = 'block';
                const mins = Math.floor(result.audio_duration_seconds / 60);
                const secs = Math.floor(result.audio_duration_seconds % 60);
                document.getElementById('podcast-stats').textContent = mins + ':' + secs.toString().padStart(2, '0') + ' duration';

                const audioFile = result.podcast_audio_path.split('/').pop();
                document.getElementById('download-audio').href = '/files/' + audioFile;
                document.getElementById('audio-player').src = '/files/' + audioFile;
            }

            function togglePreview() {
                const p = document.getElementById('preview');
                p.style.display = p.style.display === 'none' ? 'block' : 'none';
            }

            function openEditor() {
                // Save result to sessionStorage for the editor to load
                sessionStorage.setItem('generationResult', JSON.stringify({
                    topic: result.topic,
                    newsletter_html: document.getElementById('preview').innerHTML
                }));
                // Open editor with load parameter
                window.location.href = '/editor?load=generation';
            }

            async function sendNewsletter() {
                const emailInput = document.getElementById('recipient-email');
                const statusDiv = document.getElementById('email-status');
                const emails = emailInput.value.split(',').map(e => e.trim()).filter(e => e);

                if (emails.length === 0) {
                    statusDiv.className = 'status-message error';
                    statusDiv.textContent = 'Please enter at least one email address';
                    return;
                }

                statusDiv.className = 'status-message';
                statusDiv.style.display = 'block';
                statusDiv.textContent = 'Sending...';
                statusDiv.style.background = 'rgba(0, 212, 255, 0.2)';
                statusDiv.style.color = '#00d4ff';

                try {
                    const response = await fetch('/api/send-newsletter', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            newsletter_html_path: result.newsletter_html_path,
                            subject: result.topic || 'Newsletter',
                            recipients: emails,
                        }),
                    });

                    const data = await response.json();

                    if (data.success) {
                        statusDiv.className = 'status-message success';
                        if (data.provider === 'local') {
                            statusDiv.textContent = 'Demo mode: Email saved locally to output/emails/';
                        } else {
                            statusDiv.textContent = `Sent to ${data.recipients_count} recipient(s) via ${data.provider}`;
                        }
                    } else {
                        statusDiv.className = 'status-message error';
                        statusDiv.textContent = data.error || 'Failed to send';
                    }
                } catch (error) {
                    statusDiv.className = 'status-message error';
                    statusDiv.textContent = error.message;
                }
            }

            async function createRSSFeed() {
                const titleInput = document.getElementById('podcast-title');
                const statusDiv = document.getElementById('rss-status');

                if (!titleInput.value.trim()) {
                    statusDiv.className = 'status-message error';
                    statusDiv.textContent = 'Please enter a podcast name';
                    return;
                }

                try {
                    // Create the feed
                    const createResponse = await fetch('/api/rss/create', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            title: titleInput.value,
                            description: 'AI-generated podcast about ' + (result.topic || 'various topics'),
                        }),
                    });

                    const createData = await createResponse.json();

                    if (!createData.success) {
                        throw new Error(createData.error || 'Failed to create feed');
                    }

                    // Add the episode
                    const addResponse = await fetch('/api/rss/add-episode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            feed_id: createData.feed_id,
                            audio_path: result.podcast_audio_path,
                            title: result.topic || 'Episode 1',
                            description: 'AI-generated episode about ' + (result.topic || 'various topics'),
                            duration_seconds: result.audio_duration_seconds || 360,
                        }),
                    });

                    const addData = await addResponse.json();

                    if (addData.success) {
                        document.getElementById('rss-create-section').style.display = 'none';
                        document.getElementById('rss-result-section').style.display = 'block';
                        document.getElementById('rss-url').value = createData.rss_url;

                        statusDiv.className = 'status-message success';
                        statusDiv.textContent = 'RSS feed created with episode!';
                    } else {
                        throw new Error(addData.error || 'Failed to add episode');
                    }
                } catch (error) {
                    statusDiv.className = 'status-message error';
                    statusDiv.textContent = error.message;
                }
            }

            function copyRSSUrl() {
                const urlInput = document.getElementById('rss-url');
                urlInput.select();
                document.execCommand('copy');

                const statusDiv = document.getElementById('rss-status');
                statusDiv.className = 'status-message success';
                statusDiv.textContent = 'URL copied to clipboard!';
            }
        </script>
    </body>
    </html>
    """


# ============== NEWSLETTER EDITOR PAGE ==============

EDITOR_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Editor - PodcastOS</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg: #0a0a0f;
            --card: #12121a;
            --border: rgba(255,255,255,0.1);
            --cyan: #00d4ff;
            --purple: #7b2cbf;
            --green: #00ff88;
            --text: #ffffff;
            --text-dim: #888;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        /* Header */
        .editor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 30px;
            background: var(--card);
            border-bottom: 1px solid var(--border);
        }

        .logo {
            font-size: 1.3rem;
            font-weight: 700;
            background: linear-gradient(90deg, var(--cyan), var(--purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-decoration: none;
        }

        .header-actions {
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 500;
            cursor: pointer;
            border: none;
            font-size: 0.9rem;
            transition: all 0.2s;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.3);
        }

        .btn-secondary {
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text);
        }

        .btn-success {
            background: var(--green);
            color: #000;
        }

        /* Main Layout */
        .editor-layout {
            display: grid;
            grid-template-columns: 280px 1fr 320px;
            height: calc(100vh - 60px);
        }

        /* Sidebar - Block Types */
        .sidebar {
            background: var(--card);
            border-right: 1px solid var(--border);
            padding: 20px;
            overflow-y: auto;
        }

        .sidebar h3 {
            font-size: 0.85rem;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 15px;
            letter-spacing: 1px;
        }

        .block-types {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .block-type {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            cursor: grab;
            transition: all 0.2s;
        }

        .block-type:hover {
            border-color: var(--cyan);
            transform: translateX(3px);
        }

        .block-type.dragging {
            opacity: 0.5;
            cursor: grabbing;
        }

        .block-icon {
            font-size: 1.4rem;
        }

        .block-info h4 {
            font-size: 0.95rem;
            margin-bottom: 2px;
        }

        .block-info p {
            font-size: 0.75rem;
            color: var(--text-dim);
        }

        /* Canvas - Main Editor Area */
        .canvas {
            background: #1a1a24;
            padding: 30px;
            overflow-y: auto;
        }

        .canvas-inner {
            max-width: 650px;
            margin: 0 auto;
            background: #ffffff;
            min-height: 800px;
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }

        .newsletter-preview {
            color: #333;
            padding: 40px;
        }

        .drop-zone {
            border: 2px dashed var(--border);
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            color: var(--text-dim);
            margin: 10px 0;
            transition: all 0.2s;
        }

        .drop-zone.drag-over {
            border-color: var(--cyan);
            background: rgba(0, 212, 255, 0.1);
        }

        /* Newsletter Block Styles */
        .newsletter-block {
            position: relative;
            margin-bottom: 20px;
            border: 2px solid transparent;
            border-radius: 8px;
            transition: all 0.2s;
        }

        .newsletter-block:hover {
            border-color: var(--cyan);
        }

        .newsletter-block.selected {
            border-color: var(--purple);
        }

        .block-controls {
            position: absolute;
            top: -12px;
            right: 10px;
            display: none;
            gap: 5px;
        }

        .newsletter-block:hover .block-controls {
            display: flex;
        }

        .block-btn {
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85rem;
        }

        .block-btn:hover {
            background: var(--purple);
        }

        .block-btn.delete:hover {
            background: #dc3545;
        }

        /* Block Content Styles */
        .block-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .block-header h1 {
            font-size: 2rem;
            margin-bottom: 10px;
        }

        .block-header p {
            opacity: 0.8;
        }

        .block-text {
            padding: 20px;
        }

        .block-text h2 {
            font-size: 1.4rem;
            margin-bottom: 15px;
            color: #1a1a2e;
        }

        .block-text p {
            line-height: 1.7;
            color: #444;
        }

        .block-highlight {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-left: 4px solid var(--purple);
            padding: 25px;
            margin: 0;
        }

        .block-highlight h3 {
            color: var(--purple);
            margin-bottom: 10px;
        }

        .block-quote {
            padding: 25px;
            font-style: italic;
            border-left: 4px solid var(--cyan);
            background: #f8f9fa;
            color: #555;
        }

        .block-cta {
            text-align: center;
            padding: 40px;
            background: linear-gradient(135deg, var(--cyan) 0%, var(--purple) 100%);
            color: white;
        }

        .block-cta h3 {
            margin-bottom: 15px;
        }

        .block-cta .cta-button {
            display: inline-block;
            padding: 12px 30px;
            background: white;
            color: var(--purple);
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
        }

        .block-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, #ddd, transparent);
            margin: 30px 0;
        }

        .block-footer {
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            color: #666;
            font-size: 0.85rem;
        }

        /* Properties Panel */
        .properties {
            background: var(--card);
            border-left: 1px solid var(--border);
            padding: 20px;
            overflow-y: auto;
        }

        .properties h3 {
            font-size: 0.85rem;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 20px;
            letter-spacing: 1px;
        }

        .property-group {
            margin-bottom: 20px;
        }

        .property-group label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-dim);
            margin-bottom: 8px;
        }

        .property-group input,
        .property-group textarea,
        .property-group select {
            width: 100%;
            padding: 10px 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.9rem;
        }

        .property-group input:focus,
        .property-group textarea:focus {
            outline: none;
            border-color: var(--cyan);
        }

        .property-group textarea {
            min-height: 100px;
            resize: vertical;
        }

        .color-picker {
            display: flex;
            gap: 8px;
        }

        .color-swatch {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
        }

        .color-swatch:hover,
        .color-swatch.selected {
            border-color: white;
            transform: scale(1.1);
        }

        /* Status Messages */
        .status-toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 10px;
            background: var(--card);
            border: 1px solid var(--green);
            color: var(--green);
            display: none;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        }

        .status-toast.error {
            border-color: #dc3545;
            color: #dc3545;
        }

        @keyframes slideIn {
            from {
                transform: translateY(20px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: var(--card);
            border-radius: 16px;
            padding: 30px;
            max-width: 500px;
            width: 90%;
        }

        .modal-content h2 {
            margin-bottom: 20px;
        }

        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }

        /* Empty State */
        .empty-canvas {
            text-align: center;
            padding: 80px 40px;
            color: #888;
        }

        .empty-canvas h2 {
            margin-bottom: 15px;
            color: #333;
        }

        .empty-canvas p {
            margin-bottom: 30px;
        }

        .empty-canvas .btn {
            background: var(--purple);
            color: white;
        }
    </style>
</head>
<body>
    <header class="editor-header">
        <a href="/app" class="logo">PodcastOS</a>
        <div class="header-actions">
            <button class="btn btn-secondary" onclick="loadTemplate()">Load Template</button>
            <button class="btn btn-secondary" onclick="saveAsDraft()">Save Draft</button>
            <button class="btn btn-primary" onclick="exportHTML()">Export HTML</button>
            <button class="btn btn-success" onclick="sendNewsletter()">Send Email</button>
        </div>
    </header>

    <div class="editor-layout">
        <!-- Sidebar - Block Types -->
        <aside class="sidebar">
            <h3>Content Blocks</h3>
            <div class="block-types">
                <div class="block-type" draggable="true" data-type="header">
                    <span class="block-icon">📰</span>
                    <div class="block-info">
                        <h4>Header</h4>
                        <p>Newsletter title & intro</p>
                    </div>
                </div>
                <div class="block-type" draggable="true" data-type="text">
                    <span class="block-icon">📝</span>
                    <div class="block-info">
                        <h4>Text Section</h4>
                        <p>Rich text content</p>
                    </div>
                </div>
                <div class="block-type" draggable="true" data-type="highlight">
                    <span class="block-icon">💡</span>
                    <div class="block-info">
                        <h4>Key Insight</h4>
                        <p>Highlighted callout</p>
                    </div>
                </div>
                <div class="block-type" draggable="true" data-type="quote">
                    <span class="block-icon">💬</span>
                    <div class="block-info">
                        <h4>Quote</h4>
                        <p>Blockquote style</p>
                    </div>
                </div>
                <div class="block-type" draggable="true" data-type="cta">
                    <span class="block-icon">🎯</span>
                    <div class="block-info">
                        <h4>Call to Action</h4>
                        <p>Button with link</p>
                    </div>
                </div>
                <div class="block-type" draggable="true" data-type="divider">
                    <span class="block-icon">➖</span>
                    <div class="block-info">
                        <h4>Divider</h4>
                        <p>Section separator</p>
                    </div>
                </div>
                <div class="block-type" draggable="true" data-type="footer">
                    <span class="block-icon">📧</span>
                    <div class="block-info">
                        <h4>Footer</h4>
                        <p>Unsubscribe & info</p>
                    </div>
                </div>
            </div>

            <h3 style="margin-top: 30px;">Templates</h3>
            <div class="block-types">
                <div class="block-type" onclick="loadDefaultTemplate()">
                    <span class="block-icon">✨</span>
                    <div class="block-info">
                        <h4>Default Newsletter</h4>
                        <p>Start with a template</p>
                    </div>
                </div>
            </div>
        </aside>

        <!-- Main Canvas -->
        <main class="canvas">
            <div class="canvas-inner">
                <div class="newsletter-preview" id="newsletter-canvas">
                    <div class="empty-canvas" id="empty-state">
                        <h2>Start Building Your Newsletter</h2>
                        <p>Drag blocks from the sidebar or load a generated newsletter</p>
                        <button class="btn" onclick="loadFromGeneration()">Load Generated Content</button>
                    </div>
                </div>
            </div>
        </main>

        <!-- Properties Panel -->
        <aside class="properties" id="properties-panel">
            <h3>Block Properties</h3>
            <div id="property-fields">
                <p style="color: var(--text-dim);">Select a block to edit its properties</p>
            </div>
        </aside>
    </div>

    <!-- Send Email Modal -->
    <div class="modal" id="send-modal">
        <div class="modal-content">
            <h2>Send Newsletter</h2>
            <div class="property-group">
                <label>Subject Line</label>
                <input type="text" id="email-subject" placeholder="Your newsletter subject">
            </div>
            <div class="property-group">
                <label>Recipients (comma-separated)</label>
                <textarea id="email-recipients" placeholder="email1@example.com, email2@example.com"></textarea>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeSendModal()">Cancel</button>
                <button class="btn btn-success" onclick="confirmSend()">Send Now</button>
            </div>
        </div>
    </div>

    <!-- Status Toast -->
    <div class="status-toast" id="status-toast"></div>

    <script>
        // Newsletter blocks data
        let blocks = [];
        let selectedBlockId = null;

        // Block templates
        const blockTemplates = {
            header: {
                type: 'header',
                title: 'Your Newsletter Title',
                subtitle: 'Weekly insights and updates',
                bgColor: '#1a1a2e'
            },
            text: {
                type: 'text',
                heading: 'Section Title',
                content: 'Add your content here. This section supports rich text formatting.'
            },
            highlight: {
                type: 'highlight',
                heading: 'Key Takeaway',
                content: 'Your most important insight goes here.'
            },
            quote: {
                type: 'quote',
                content: '"Add a compelling quote here."',
                author: '- Author Name'
            },
            cta: {
                type: 'cta',
                heading: 'Ready to take action?',
                buttonText: 'Get Started',
                buttonUrl: '#'
            },
            divider: {
                type: 'divider'
            },
            footer: {
                type: 'footer',
                content: 'You received this email because you subscribed to our newsletter.\\nUnsubscribe | Update Preferences'
            }
        };

        // Initialize drag and drop
        document.querySelectorAll('.block-type[draggable]').forEach(block => {
            block.addEventListener('dragstart', handleDragStart);
            block.addEventListener('dragend', handleDragEnd);
        });

        function handleDragStart(e) {
            e.target.classList.add('dragging');
            e.dataTransfer.setData('blockType', e.target.dataset.type);
        }

        function handleDragEnd(e) {
            e.target.classList.remove('dragging');
        }

        // Canvas drop handling
        const canvas = document.getElementById('newsletter-canvas');

        canvas.addEventListener('dragover', (e) => {
            e.preventDefault();
            canvas.classList.add('drag-over');
        });

        canvas.addEventListener('dragleave', () => {
            canvas.classList.remove('drag-over');
        });

        canvas.addEventListener('drop', (e) => {
            e.preventDefault();
            canvas.classList.remove('drag-over');

            const blockType = e.dataTransfer.getData('blockType');
            if (blockType) {
                addBlock(blockType);
            }
        });

        // Add a new block
        function addBlock(type, data = null) {
            const id = 'block-' + Date.now();
            const blockData = data || { ...blockTemplates[type], id };
            blockData.id = id;

            blocks.push(blockData);
            renderBlocks();
            selectBlock(id);

            // Hide empty state
            document.getElementById('empty-state').style.display = 'none';
        }

        // Render all blocks
        function renderBlocks() {
            const container = document.getElementById('newsletter-canvas');
            const emptyState = document.getElementById('empty-state');

            // Clear and keep empty state
            container.innerHTML = '';
            container.appendChild(emptyState);

            if (blocks.length === 0) {
                emptyState.style.display = 'block';
                return;
            }

            emptyState.style.display = 'none';

            blocks.forEach((block, index) => {
                const el = createBlockElement(block, index);
                container.appendChild(el);
            });
        }

        // Create block element
        function createBlockElement(block, index) {
            const wrapper = document.createElement('div');
            wrapper.className = 'newsletter-block' + (block.id === selectedBlockId ? ' selected' : '');
            wrapper.dataset.id = block.id;
            wrapper.draggable = true;

            // Controls
            wrapper.innerHTML = `
                <div class="block-controls">
                    <button class="block-btn" onclick="moveBlock('${block.id}', -1)" title="Move up">↑</button>
                    <button class="block-btn" onclick="moveBlock('${block.id}', 1)" title="Move down">↓</button>
                    <button class="block-btn" onclick="duplicateBlock('${block.id}')" title="Duplicate">⧉</button>
                    <button class="block-btn delete" onclick="deleteBlock('${block.id}')" title="Delete">✕</button>
                </div>
            `;

            // Content based on type
            const content = document.createElement('div');
            content.className = 'block-' + block.type;

            switch (block.type) {
                case 'header':
                    content.style.background = block.bgColor || '#1a1a2e';
                    content.innerHTML = `
                        <h1>${block.title}</h1>
                        <p>${block.subtitle}</p>
                    `;
                    break;
                case 'text':
                    content.innerHTML = `
                        <h2>${block.heading}</h2>
                        <p>${block.content}</p>
                    `;
                    break;
                case 'highlight':
                    content.innerHTML = `
                        <h3>${block.heading}</h3>
                        <p>${block.content}</p>
                    `;
                    break;
                case 'quote':
                    content.innerHTML = `
                        <p>${block.content}</p>
                        <p><strong>${block.author || ''}</strong></p>
                    `;
                    break;
                case 'cta':
                    content.innerHTML = `
                        <h3>${block.heading}</h3>
                        <a href="${block.buttonUrl}" class="cta-button">${block.buttonText}</a>
                    `;
                    break;
                case 'divider':
                    // Just the divider class styles it
                    break;
                case 'footer':
                    content.innerHTML = `<p>${(block.content || '').replace(/\\n/g, '<br>')}</p>`;
                    break;
            }

            wrapper.appendChild(content);

            // Click to select
            wrapper.addEventListener('click', (e) => {
                if (!e.target.closest('.block-controls')) {
                    selectBlock(block.id);
                }
            });

            // Drag to reorder
            wrapper.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('blockId', block.id);
            });

            return wrapper;
        }

        // Select a block
        function selectBlock(id) {
            selectedBlockId = id;
            renderBlocks();
            showBlockProperties(id);
        }

        // Show properties for selected block
        function showBlockProperties(id) {
            const block = blocks.find(b => b.id === id);
            if (!block) return;

            const panel = document.getElementById('property-fields');
            let html = '';

            switch (block.type) {
                case 'header':
                    html = `
                        <div class="property-group">
                            <label>Title</label>
                            <input type="text" value="${block.title}" onchange="updateBlock('${id}', 'title', this.value)">
                        </div>
                        <div class="property-group">
                            <label>Subtitle</label>
                            <input type="text" value="${block.subtitle}" onchange="updateBlock('${id}', 'subtitle', this.value)">
                        </div>
                        <div class="property-group">
                            <label>Background Color</label>
                            <div class="color-picker">
                                <div class="color-swatch" style="background:#1a1a2e" onclick="updateBlock('${id}', 'bgColor', '#1a1a2e')"></div>
                                <div class="color-swatch" style="background:#7b2cbf" onclick="updateBlock('${id}', 'bgColor', '#7b2cbf')"></div>
                                <div class="color-swatch" style="background:#00d4ff" onclick="updateBlock('${id}', 'bgColor', '#00d4ff')"></div>
                                <div class="color-swatch" style="background:#00ff88" onclick="updateBlock('${id}', 'bgColor', '#00ff88')"></div>
                                <div class="color-swatch" style="background:#dc3545" onclick="updateBlock('${id}', 'bgColor', '#dc3545')"></div>
                            </div>
                        </div>
                    `;
                    break;
                case 'text':
                    html = `
                        <div class="property-group">
                            <label>Heading</label>
                            <input type="text" value="${block.heading}" onchange="updateBlock('${id}', 'heading', this.value)">
                        </div>
                        <div class="property-group">
                            <label>Content</label>
                            <textarea onchange="updateBlock('${id}', 'content', this.value)">${block.content}</textarea>
                        </div>
                    `;
                    break;
                case 'highlight':
                    html = `
                        <div class="property-group">
                            <label>Heading</label>
                            <input type="text" value="${block.heading}" onchange="updateBlock('${id}', 'heading', this.value)">
                        </div>
                        <div class="property-group">
                            <label>Content</label>
                            <textarea onchange="updateBlock('${id}', 'content', this.value)">${block.content}</textarea>
                        </div>
                    `;
                    break;
                case 'quote':
                    html = `
                        <div class="property-group">
                            <label>Quote</label>
                            <textarea onchange="updateBlock('${id}', 'content', this.value)">${block.content}</textarea>
                        </div>
                        <div class="property-group">
                            <label>Author</label>
                            <input type="text" value="${block.author || ''}" onchange="updateBlock('${id}', 'author', this.value)">
                        </div>
                    `;
                    break;
                case 'cta':
                    html = `
                        <div class="property-group">
                            <label>Heading</label>
                            <input type="text" value="${block.heading}" onchange="updateBlock('${id}', 'heading', this.value)">
                        </div>
                        <div class="property-group">
                            <label>Button Text</label>
                            <input type="text" value="${block.buttonText}" onchange="updateBlock('${id}', 'buttonText', this.value)">
                        </div>
                        <div class="property-group">
                            <label>Button URL</label>
                            <input type="text" value="${block.buttonUrl}" onchange="updateBlock('${id}', 'buttonUrl', this.value)">
                        </div>
                    `;
                    break;
                case 'footer':
                    html = `
                        <div class="property-group">
                            <label>Footer Content</label>
                            <textarea onchange="updateBlock('${id}', 'content', this.value)">${block.content}</textarea>
                        </div>
                    `;
                    break;
                case 'divider':
                    html = '<p style="color: var(--text-dim);">This block has no editable properties.</p>';
                    break;
            }

            panel.innerHTML = html;
        }

        // Update block property
        function updateBlock(id, property, value) {
            const block = blocks.find(b => b.id === id);
            if (block) {
                block[property] = value;
                renderBlocks();
            }
        }

        // Move block
        function moveBlock(id, direction) {
            const index = blocks.findIndex(b => b.id === id);
            const newIndex = index + direction;

            if (newIndex >= 0 && newIndex < blocks.length) {
                const [block] = blocks.splice(index, 1);
                blocks.splice(newIndex, 0, block);
                renderBlocks();
            }
        }

        // Duplicate block
        function duplicateBlock(id) {
            const block = blocks.find(b => b.id === id);
            if (block) {
                const newBlock = { ...block, id: 'block-' + Date.now() };
                const index = blocks.findIndex(b => b.id === id);
                blocks.splice(index + 1, 0, newBlock);
                renderBlocks();
                showToast('Block duplicated');
            }
        }

        // Delete block
        function deleteBlock(id) {
            blocks = blocks.filter(b => b.id !== id);
            selectedBlockId = null;
            renderBlocks();
            document.getElementById('property-fields').innerHTML = '<p style="color: var(--text-dim);">Select a block to edit its properties</p>';
            showToast('Block deleted');
        }

        // Load default template
        function loadDefaultTemplate() {
            blocks = [
                { ...blockTemplates.header, id: 'block-1', title: 'Weekly Insights', subtitle: 'Your weekly dose of knowledge' },
                { ...blockTemplates.text, id: 'block-2', heading: 'Welcome', content: 'Thank you for subscribing to our newsletter. Each week, we bring you the latest insights and updates.' },
                { ...blockTemplates.highlight, id: 'block-3', heading: 'This Week\\'s Key Insight', content: 'The most important takeaway that you should remember.' },
                { ...blockTemplates.divider, id: 'block-4' },
                { ...blockTemplates.text, id: 'block-5', heading: 'Main Story', content: 'Your main content goes here. Share your thoughts, insights, and valuable information with your readers.' },
                { ...blockTemplates.quote, id: 'block-6', content: '"Innovation distinguishes between a leader and a follower."', author: '- Steve Jobs' },
                { ...blockTemplates.cta, id: 'block-7' },
                { ...blockTemplates.footer, id: 'block-8', content: 'You received this because you subscribed.\\nUnsubscribe | View in browser' }
            ];
            renderBlocks();
            showToast('Template loaded');
        }

        // Load from generated content
        async function loadFromGeneration() {
            // Check if there's a generation result in sessionStorage
            const resultStr = sessionStorage.getItem('generationResult');
            if (resultStr) {
                try {
                    const result = JSON.parse(resultStr);
                    if (result.newsletter_html) {
                        // Parse the generated newsletter into blocks
                        parseGeneratedNewsletter(result.newsletter_html, result.topic);
                        showToast('Generated content loaded');
                        return;
                    }
                } catch (e) {
                    console.error('Error parsing generation result:', e);
                }
            }

            // Fallback - try to fetch latest generation
            showToast('No recent generation found. Loading template instead.', true);
            loadDefaultTemplate();
        }

        // Parse generated newsletter HTML into blocks
        function parseGeneratedNewsletter(html, topic) {
            // Create a temporary div to parse HTML
            const temp = document.createElement('div');
            temp.innerHTML = html;

            blocks = [];

            // Add header
            blocks.push({
                ...blockTemplates.header,
                id: 'block-' + Date.now(),
                title: topic || 'Your Newsletter',
                subtitle: 'AI-Generated Content'
            });

            // Find sections and convert to blocks
            const sections = temp.querySelectorAll('section, .section, article, div > h2, div > h3');

            if (sections.length === 0) {
                // Simple conversion - just add as text block
                blocks.push({
                    ...blockTemplates.text,
                    id: 'block-' + (Date.now() + 1),
                    heading: 'Content',
                    content: temp.textContent.substring(0, 500) + '...'
                });
            } else {
                sections.forEach((section, i) => {
                    const heading = section.querySelector('h2, h3')?.textContent || 'Section ' + (i + 1);
                    const content = section.textContent.replace(heading, '').trim().substring(0, 400);

                    blocks.push({
                        ...blockTemplates.text,
                        id: 'block-' + (Date.now() + i + 1),
                        heading: heading,
                        content: content
                    });
                });
            }

            // Add footer
            blocks.push({
                ...blockTemplates.footer,
                id: 'block-footer',
                content: 'Generated with PodcastOS\\nUnsubscribe | View in browser'
            });

            renderBlocks();
        }

        // Export as HTML
        function exportHTML() {
            const html = generateFinalHTML();

            // Create download
            const blob = new Blob([html], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'newsletter.html';
            a.click();
            URL.revokeObjectURL(url);

            showToast('Newsletter exported');
        }

        // Generate final HTML for email
        function generateFinalHTML() {
            let html = `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter</title>
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: #ffffff; }
        .header { background: #1a1a2e; color: white; padding: 40px; text-align: center; }
        .header h1 { margin: 0 0 10px; font-size: 28px; }
        .header p { margin: 0; opacity: 0.8; }
        .section { padding: 30px 40px; }
        .section h2 { color: #1a1a2e; margin: 0 0 15px; }
        .section p { color: #444; line-height: 1.7; margin: 0; }
        .highlight { background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-left: 4px solid #7b2cbf; padding: 25px 40px; }
        .highlight h3 { color: #7b2cbf; margin: 0 0 10px; }
        .quote { padding: 25px 40px; font-style: italic; border-left: 4px solid #00d4ff; background: #f8f9fa; color: #555; }
        .cta { text-align: center; padding: 40px; background: linear-gradient(135deg, #00d4ff, #7b2cbf); color: white; }
        .cta h3 { margin: 0 0 15px; }
        .cta a { display: inline-block; padding: 12px 30px; background: white; color: #7b2cbf; border-radius: 25px; text-decoration: none; font-weight: 600; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #ddd, transparent); margin: 30px 40px; }
        .footer { text-align: center; padding: 30px; background: #f8f9fa; color: #666; font-size: 14px; }
    </style>
</head>
<body>
<div class="container">
`;

            blocks.forEach(block => {
                switch (block.type) {
                    case 'header':
                        html += `<div class="header" style="background: ${block.bgColor || '#1a1a2e'}">
    <h1>${block.title}</h1>
    <p>${block.subtitle}</p>
</div>
`;
                        break;
                    case 'text':
                        html += `<div class="section">
    <h2>${block.heading}</h2>
    <p>${block.content}</p>
</div>
`;
                        break;
                    case 'highlight':
                        html += `<div class="highlight">
    <h3>${block.heading}</h3>
    <p>${block.content}</p>
</div>
`;
                        break;
                    case 'quote':
                        html += `<div class="quote">
    <p>${block.content}</p>
    <p><strong>${block.author || ''}</strong></p>
</div>
`;
                        break;
                    case 'cta':
                        html += `<div class="cta">
    <h3>${block.heading}</h3>
    <a href="${block.buttonUrl}">${block.buttonText}</a>
</div>
`;
                        break;
                    case 'divider':
                        html += '<div class="divider"></div>\n';
                        break;
                    case 'footer':
                        html += `<div class="footer">
    <p>${(block.content || '').replace(/\\\\n/g, '<br>')}</p>
</div>
`;
                        break;
                }
            });

            html += `</div>
</body>
</html>`;

            return html;
        }

        // Save as draft
        async function saveAsDraft() {
            try {
                const response = await fetch('/api/newsletter/save-draft', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: 'Newsletter Draft',
                        blocks: blocks,
                        html: generateFinalHTML()
                    })
                });

                const data = await response.json();
                if (data.success) {
                    showToast('Draft saved');
                } else {
                    showToast('Failed to save: ' + data.error, true);
                }
            } catch (e) {
                showToast('Error saving draft', true);
            }
        }

        // Load template
        async function loadTemplate() {
            // For now, just load default
            loadDefaultTemplate();
        }

        // Send newsletter
        function sendNewsletter() {
            if (blocks.length === 0) {
                showToast('Add some content first', true);
                return;
            }
            document.getElementById('send-modal').classList.add('active');
        }

        function closeSendModal() {
            document.getElementById('send-modal').classList.remove('active');
        }

        async function confirmSend() {
            const subject = document.getElementById('email-subject').value;
            const recipients = document.getElementById('email-recipients').value;

            if (!subject || !recipients) {
                showToast('Please fill in all fields', true);
                return;
            }

            try {
                const response = await fetch('/api/send-newsletter', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        html: generateFinalHTML(),
                        subject: subject,
                        recipients: recipients.split(',').map(e => e.trim())
                    })
                });

                const data = await response.json();
                if (data.success) {
                    closeSendModal();
                    showToast('Newsletter sent to ' + data.recipients_count + ' recipients');
                } else {
                    showToast('Failed to send: ' + data.error, true);
                }
            } catch (e) {
                showToast('Error sending newsletter', true);
            }
        }

        // Show toast notification
        function showToast(message, isError = false) {
            const toast = document.getElementById('status-toast');
            toast.textContent = message;
            toast.className = 'status-toast' + (isError ? ' error' : '');
            toast.style.display = 'block';

            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            // Check for generation data
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('load') === 'generation') {
                loadFromGeneration();
            }
        });
    </script>
</body>
</html>
"""


@app.get("/editor", response_class=HTMLResponse)
async def editor_page():
    """Newsletter editor page."""
    return EDITOR_PAGE


# ============== NEWSLETTER API ENDPOINTS ==============

class SaveDraftRequest(BaseModel):
    title: str
    blocks: list
    html: str


@app.post("/api/newsletter/save-draft")
async def save_newsletter_draft(request: SaveDraftRequest):
    """Save a newsletter draft."""
    try:
        from .database import get_supabase

        supabase = get_supabase()

        # Save to database
        result = supabase.table("newsletter_drafts").insert({
            "title": request.title,
            "json_content": request.blocks,
            "html_content": request.html,
            "status": "draft"
        }).execute()

        if result.data:
            return {"success": True, "draft_id": result.data[0].get("id")}
        return {"success": False, "error": "Failed to save draft"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/newsletter/drafts")
async def get_newsletter_drafts():
    """Get all newsletter drafts."""
    try:
        from .database import get_supabase

        supabase = get_supabase()
        result = supabase.table("newsletter_drafts").select("*").order("created_at", desc=True).execute()

        return {"success": True, "drafts": result.data}
    except Exception as e:
        return {"success": False, "error": str(e), "drafts": []}


@app.get("/api/newsletter/draft/{draft_id}")
async def get_newsletter_draft(draft_id: str):
    """Get a specific newsletter draft."""
    try:
        from .database import get_supabase

        supabase = get_supabase()
        result = supabase.table("newsletter_drafts").select("*").eq("id", draft_id).single().execute()

        if result.data:
            return {"success": True, "draft": result.data}
        return {"success": False, "error": "Draft not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
