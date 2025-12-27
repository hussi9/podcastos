"""
Hybrid Research Engine: Social Media First + Google Deep Research
Combines community insights with comprehensive web research
"""
import os
import asyncio
from typing import Dict, List
from datetime import datetime
import praw
from src.intelligence.research.gemini_deep_research import GeminiDeepResearch


class HybridResearchEngine:
    """
    Two-stage research:
    1. Social Media (Reddit, Twitter/X) - Real-time community insights
    2. Google Deep Research - Comprehensive web analysis + verification
    
    Best of both worlds!
    """
    
    def __init__(self):
        # Stage 1: Social Media
        self.reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent="PodcastResearcher/1.0"
        )
        
        # Stage 2: Google Deep Research
        self.deep_research = GeminiDeepResearch()
    
    async def research_topic(
        self,
        topic: str,
        subreddits: List[str] = None,
        context: str = ""
    ) -> Dict:
        """
        Complete hybrid research workflow
        
        Args:
            topic: Topic to research
            subreddits: Subreddits to search (e.g., ['immigration', 'h1b'])
            context: Additional context about the podcast/audience
            
        Returns:
            {
                "topic": "...",
                "social_insights": {...},  # From Reddit/Twitter
                "web_research": {...},     # From Google Deep Research
                "combined_summary": "...", # AI synthesis of both
                "sources": [...],          # All sources combined
                "confidence": 0.95
            }
        """
        
        print(f"\n{'='*60}")
        print(f"HYBRID RESEARCH: {topic}")
        print(f"{'='*60}\n")
        
        # STAGE 1: Social Media Research
        print("📱 STAGE 1: Social Media Insights")
        print("-" * 60)
        social_insights = await self._research_social_media(topic, subreddits)
        
        # STAGE 2: Google Deep Research (enriched with social context)
        print("\n🔍 STAGE 2: Google Deep Research")
        print("-" * 60)
        
        # Enhance Deep Research with social insights
        enriched_context = f"""
        {context}
        
        Social Media Context (from Reddit):
        - Community talking points: {', '.join(social_insights['trending_themes'][:5])}
        - Top concerns: {', '.join(social_insights['community_concerns'][:3])}
        - Engagement level: {social_insights['engagement_score']:.0%}
        """
        
        web_research = await self.deep_research.research_topic(
            topic=topic,
            context=enriched_context
        )
        
        # STAGE 3: Synthesize both sources
        print("\n🧠 STAGE 3: Synthesizing Insights")
        print("-" * 60)
        combined = await self._synthesize_research(
            social_insights, web_research, topic
        )
        
        return {
            "topic": topic,
            "social_insights": social_insights,
            "web_research": web_research,
            "combined_summary": combined["summary"],
            "key_facts": combined["key_facts"],
            "sources": combined["sources"],
            "confidence": combined["confidence"],
            "research_date": datetime.utcnow().isoformat()
        }
    
    async def _research_social_media(
        self,
        topic: str,
        subreddits: List[str] = None
    ) -> Dict:
        """Stage 1: Reddit + Twitter/X research"""
        
        if not subreddits:
            # Default immigration-focused subreddits
            subreddits = [
                "immigration",
                "h1b",
                "greencard",
                "cscareerquestions",
                "india"
            ]
        
        reddit_data = {
            "posts": [],
            "trending_themes": [],
            "community_concerns": [],
            "engagement_score": 0.0,
            "source_count": 0
        }
        
        try:
            # Search Reddit
            for subreddit_name in subreddits:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    
                    # Search recent posts
                    for post in subreddit.search(topic, time_filter="week", limit=10):
                        reddit_data["posts"].append({
                            "title": post.title,
                            "text": post.selftext[:500],  # First 500 chars
                            "score": post.score,
                            "comments": post.num_comments,
                            "url": f"https://reddit.com{post.permalink}",
                            "subreddit": subreddit_name,
                            "created": datetime.fromtimestamp(post.created_utc).isoformat()
                        })
                        
                        print(f"  📊 r/{subreddit_name}: {post.title[:60]}... ({post.score}↑)")
                
                except Exception as e:
                    print(f"  ⚠️  Error fetching r/{subreddit_name}: {e}")
            
            # Analyze posts
            reddit_data["source_count"] = len(reddit_data["posts"])
            
            if reddit_data["posts"]:
                # Extract trending themes (most discussed topics)
                reddit_data["trending_themes"] = self._extract_themes(reddit_data["posts"])
                
                # Extract community concerns (from titles + text)
                reddit_data["community_concerns"] = self._extract_concerns(reddit_data["posts"])
                
                # Calculate engagement score
                total_engagement = sum(p["score"] + p["comments"] for p in reddit_data["posts"])
                avg_engagement = total_engagement / len(reddit_data["posts"])
                reddit_data["engagement_score"] = min(avg_engagement / 100, 1.0)  # Normalize
                
                print(f"\n  ✅ Found {len(reddit_data['posts'])} posts")
                print(f"  📈 Engagement score: {reddit_data['engagement_score']:.1%}")
        
        except Exception as e:
            print(f"  ❌ Social media research error: {e}")
        
        return reddit_data
    
    def _extract_themes(self, posts: List[Dict]) -> List[str]:
        """Extract trending themes from posts"""
        # Simple keyword extraction (could use NLP for better results)
        themes = {}
        
        for post in posts:
            # Combine title and text
            text = f"{post['title']} {post['text']}".lower()
            
            # Common immigration keywords
            keywords = [
                'h1b', 'visa', 'green card', 'uscis', 'lottery',
                'salary', 'layoff', 'sponsorship', 'l1', 'opt',
                'stem', 'cap', 'premium processing', 'rfe', 
                'approval', 'denial', 'wait time'
            ]
            
            for keyword in keywords:
                if keyword in text:
                    themes[keyword] = themes.get(keyword, 0) + 1
        
        # Sort by frequency
        sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, _ in sorted_themes[:10]]
    
    def _extract_concerns(self, posts: List[Dict]) -> List[str]:
        """Extract community concerns from posts"""
        concerns = []
        
        # Concern indicators
        indicators = [
            ('worried', 'concern', 'anxious'),
            ('problem', 'issue', 'trouble'),
            ('denied', 'rejected', 'failed'),
            ('confused', 'unclear', 'unsure'),
            ('expensive', 'costly', 'fee')
        ]
        
        for post in posts[:20]:  # Top 20 posts
            text = f"{post['title']} {post['text']}".lower()
            
            for indicator_group in indicators:
                if any(ind in text for ind in indicator_group):
                    # Extract the concern (simplified)
                    concern_text = post['title']
                    if concern_text not in concerns:
                        concerns.append(concern_text)
        
        return concerns[:5]  # Top 5 concerns
    
    async def _synthesize_research(
        self,
        social: Dict,
        web: Dict,
        topic: str
    ) -> Dict:
        """Synthesize social + web research using Gemini"""
        
        from google import genai
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        synthesis_prompt = f"""You are synthesizing research from two sources:

**SOURCE 1: Social Media (Reddit Community)**
- Posts analyzed: {social['source_count']}
- Trending themes: {', '.join(social['trending_themes'][:5])}
- Community concerns: {', '.join(social['community_concerns'][:3])}
- Engagement: {social['engagement_score']:.0%}

**SOURCE 2: Google Deep Web Research**
- Summary: {web['summary']}
- Key facts: {', '.join(web['key_facts'][:5])}
- Sources: {len(web['sources'])} verified sources

**YOUR TASK:**
Create a unified summary that:
1. Combines both perspectives (community + authoritative sources)
2. Highlights what the community is talking about vs. what official sources say
3. Identifies any gaps or contradictions
4. Provides 7-10 key facts that blend both sources
5. Rate overall confidence (0-1) based on source quality

Topic: {topic}

Return JSON:
{{
    "summary": "2-3 sentence unified summary",
    "key_facts": ["fact 1", "fact 2", ...],
    "community_perspective": "What Reddit users are saying",
    "official_perspective": "What official sources say",
    "gaps": ["gap 1", "gap 2"],
    "confidence": 0.92
}}
"""
        
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=synthesis_prompt
        )
        
        # Parse JSON
        import json
        result_text = response.text
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        
        synthesis = json.loads(result_text.strip())
        
        # Combine sources
        all_sources = []
        
        # Add Reddit sources
        for post in social['posts'][:5]:  # Top 5 Reddit posts
            all_sources.append({
                "title": post['title'],
                "url": post['url'],
                "type": "reddit",
                "score": post['score']
            })
        
        # Add web sources
        for source in web['sources'][:10]:  # Top 10 web sources
            all_sources.append({
                "title": source['title'],
                "url": source['url'],
                "type": "web"
            })
        
        synthesis["sources"] = all_sources
        
        print(f"  ✅ Synthesized {len(all_sources)} sources")
        print(f"  🎯 Confidence: {synthesis['confidence']:.1%}")
        
        return synthesis


# Integration with your workflow
class EnhancedPodcastResearchEngine:
    """
    Production research engine with hybrid approach
    """
    
    def __init__(self):
        self.hybrid_research = HybridResearchEngine()
    
    async def deep_dive(
        self,
        profile_id: int,
        topic_count: int = 5
    ) -> Dict:
        """
        Complete research workflow:
        1. Get trending topics from social media
        2. Deep research each with hybrid engine
        3. Return research bundle
        """
        
        from webapp.models import PodcastProfile
        from webapp.app import get_db
        
        db = get_db()
        profile = db.query(PodcastProfile).get(profile_id)
        
        # Get relevant subreddits from profile settings
        # (you could add this to profile config)
        subreddits = self._get_subreddits_for_profile(profile)
        
        # Discover trending topics from Reddit
        print("🔍 Discovering trending topics from social media...")
        trending_topics = await self._discover_trending_topics(subreddits)
        
        # Research each topic with hybrid approach
        print(f"\n📚 Deep researching {topic_count} topics...")
        research_results = []
        
        for topic in trending_topics[:topic_count]:
            print(f"\n{'='*60}")
            print(f"Topic {len(research_results) + 1}/{topic_count}: {topic}")
            print(f"{'='*60}")
            
            result = await self.hybrid_research.research_topic(
                topic=topic,
                subreddits=subreddits,
                context=f"Podcast: {profile.name}, Audience: {profile.target_audience}"
            )
            
            research_results.append(result)
        
        # Create research bundle
        research_bundle = {
            "profile_id": profile_id,
            "generated_at": datetime.utcnow().isoformat(),
            "topics": research_results,
            "metadata": {
                "topic_count": len(research_results),
                "total_sources": sum(len(r['sources']) for r in research_results),
                "avg_confidence": sum(r['confidence'] for r in research_results) / len(research_results)
            }
        }
        
        return research_bundle
    
    def _get_subreddits_for_profile(self, profile) -> List[str]:
        """Get relevant subreddits based on profile"""
        # Default immigration-focused
        base_subreddits = ["immigration", "h1b", "greencard"]
        
        # Could expand based on profile settings
        # if profile.topics includes "tech":
        #     base_subreddits.extend(["cscareerquestions", "programming"])
        
        return base_subreddits
    
    async def _discover_trending_topics(
        self,
        subreddits: List[str]
    ) -> List[str]:
        """Discover trending topics from subreddits"""
        
        trending = []
        
        for subreddit_name in subreddits:
            try:
                subreddit = self.hybrid_research.reddit.subreddit(subreddit_name)
                
                # Get hot posts
                for post in subreddit.hot(limit=20):
                    # Filter for immigration/visa topics
                    if any(keyword in post.title.lower() for keyword in [
                        'h1b', 'visa', 'green card', 'uscis', 'immigration',
                        'opt', 'stem', 'sponsorship'
                    ]):
                        trending.append(post.title)
                        print(f"  📈 Trending: {post.title[:60]}...")
            
            except Exception as e:
                print(f"  ⚠️  Error: {e}")
        
        # Deduplicate and return top topics
        unique_trending = list(set(trending))
        return unique_trending[:10]


# Example usage
async def test_hybrid_research():
    """Test the hybrid research engine"""
    
    engine = HybridResearchEngine()
    
    result = await engine.research_topic(
        topic="H1B visa lottery 2025 results",
        subreddits=["immigration", "h1b"],
        context="Tech-focused immigration podcast"
    )
    
    print("\n" + "="*60)
    print("HYBRID RESEARCH RESULTS")
    print("="*60)
    
    print(f"\n📊 Social Insights:")
    print(f"  - Posts analyzed: {result['social_insights']['source_count']}")
    print(f"  - Trending: {', '.join(result['social_insights']['trending_themes'][:5])}")
    print(f"  - Engagement: {result['social_insights']['engagement_score']:.0%}")
    
    print(f"\n🌐 Web Research:")
    print(f"  - {result['web_research']['summary']}")
    print(f"  - Sources: {len(result['web_research']['sources'])}")
    
    print(f"\n🎯 Combined Analysis:")
    print(f"  - {result['combined_summary']}")
    print(f"  - Confidence: {result['confidence']:.0%}")
    print(f"  - Total sources: {len(result['sources'])}")


if __name__ == "__main__":
    asyncio.run(test_hybrid_research())
