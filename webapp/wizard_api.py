"""
AI Wizard API Endpoints for Podcast Creation
Provides intelligent suggestions using Gemini at each step
"""

import os
from flask import Blueprint, request, jsonify
from google import genai

# Create blueprint
wizard_api = Blueprint('wizard_api', __name__)

# Gemini client (initialized lazily)
gemini_client = None

def get_gemini_client():
    """Get or initialize Gemini client"""
    global gemini_client
    if gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        gemini_client = genai.Client(api_key=api_key)
    return gemini_client


@wizard_api.route('/api/ai-suggest', methods=['POST'])
def ai_suggest():
    """Get AI suggestions for podcast setup"""
    data = request.json
    prompt = data.get('prompt', '')
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    client = get_gemini_client()
    if not client:
        return jsonify({
            'suggestion': get_fallback_suggestion(prompt)
        })
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt
        )
        
        return jsonify({
            'suggestion': response.text
        })
        
    except Exception as e:
        return jsonify({
            'suggestion': get_fallback_suggestion(prompt)
        })


@wizard_api.route('/api/suggest-sources', methods=['POST'])
def suggest_sources():
    """Suggest content sources based on podcast idea"""
    data = request.json
    idea = data.get('idea', '')
    audience = data.get('audience', '')
    
    client = get_gemini_client()
    
    try:
        if client:
            prompt = f"""For a podcast about "{idea}" targeting "{audience}", recommend the best 6-8 content sources.

Consider:
- Reddit subreddits
- RSS feeds
- News sites 
- YouTube channels
- Twitter accounts

Provide specific source names and why they're relevant. Format as a numbered list."""

            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            
            # Parse AI response into structured sources
            sources = parse_sources_from_ai(response.text, idea)
            
            return jsonify({
                'explanation': response.text,
                'sources': sources
            })
        else:
            # No client, use fallback
            sources = get_default_sources(idea)
            return jsonify({
                'explanation': "Here are some recommended sources based on your topic:",
                'sources': sources
            })
        
    except Exception as e:
        # Fallback sources
        sources = get_default_sources(idea)
        return jsonify({
            'explanation': "Here are some recommended sources based on your topic:",
            'sources': sources
        })


def parse_sources_from_ai(ai_text, idea):
    """Parse AI response into structured source list"""
    # For now, return smart defaults - can enhance with NLP parsing
    sources = []
    
    # Check topic keywords for smart defaults
    idea_lower = idea.lower()
    
    if 'tech' in idea_lower or 'ai' in idea_lower or 'software' in idea_lower:
        sources.extend([
            {'id': 'r/technology', 'name': 'r/technology', 'description': 'Latest tech news and discussions', 'recommended': True},
            {'id': 'r/programming', 'name': 'r/programming', 'description': 'Programming discussions', 'recommended': True},
            {'id': 'hackernews', 'name': 'Hacker News RSS', 'description': 'Tech startup news', 'recommended': True},
        ])
    
    if 'india' in idea_lower or 'desi' in idea_lower or 'indian' in idea_lower:
        sources.extend([
            {'id': 'r/india', 'name': 'r/india', 'description': 'Indian community discussions', 'recommended': True},
            {'id': 'r/ABCDesis', 'name': 'r/ABCDesis', 'description': 'American Born Confused Desis', 'recommended': True},
        ])
    
    if 'visa' in idea_lower or 'immigration' in idea_lower or 'h1b' in idea_lower:
        sources.extend([
            {'id': 'r/h1b', 'name': 'r/h1b', 'description': 'H1B visa discussions', 'recommended': True},
            {'id': 'uscis', 'name': 'USCIS News', 'description': 'Official immigration updates', 'recommended': True},
        ])
    
    if 'business' in idea_lower or 'startup' in idea_lower or 'entrepreneur' in idea_lower:
        sources.extend([
            {'id': 'r/startups', 'name': 'r/startups', 'description': 'Startup community', 'recommended': True},
            {'id': 'r/Entrepreneur', 'name': 'r/Entrepreneur', 'description': 'Entrepreneurship discussions', 'recommended': True},
        ])
    
    # Add general sources
    sources.extend([
        {'id': 'google_news', 'name': 'Google News', 'description': 'General news coverage', 'recommended': False},
        {'id': 'reddit_trending', 'name': 'Reddit Trending', 'description': 'Popular Reddit content', 'recommended': False},
    ])
    
    # Deduplicate
    seen = set()
    unique_sources = []
    for source in sources:
        if source['id'] not in seen:
            seen.add(source['id'])
            unique_sources.append(source)
    
    return unique_sources[:8]  # Limit to 8


def get_default_sources(idea):
    """Fallback sources if AI fails"""
    return [
        {'id': 'google_news', 'name': 'Google News', 'description': 'General news coverage', 'recommended': True},
        {'id': 'reddit_trending', 'name': 'Reddit Trending', 'description': 'Popular Reddit content', 'recommended': True},
        {'id': 'r/all', 'name': 'r/all', 'description': 'All of Reddit', 'recommended': False},
    ]


def get_fallback_suggestion(prompt):
    """Fallback suggestion if Gemini is unavailable"""
    if 'podcast idea' in prompt.lower() or 'refine' in prompt.lower():
        return "Consider making your podcast more specific by focusing on a niche audience and unique angle. What problem does your podcast solve for listeners?"
    elif 'audience' in prompt.lower():
        return "Be specific about demographics (age, location, profession) and psychographics (interests, pain points, goals) of your ideal listener."
    elif 'tone' in prompt.lower() or 'settings' in prompt.lower():
        return "For most podcasts, a conversational tone with 10-15 minute episodes works well. Consider your audience's listening context."
    else:
        return "Focus on creating value for a specific audience with consistent, high-quality content."
