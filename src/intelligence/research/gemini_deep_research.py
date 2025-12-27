"""
Google Gemini Deep Research Integration
Uses the Interactions API for autonomous multi-step research
"""
import os
import asyncio
import time
from typing import List, Dict
from google import genai
from google.genai import types


class GeminiDeepResearch:
    """
    Autonomous research agent using Gemini Deep Research
    via the Interactions API
    """
    
    def __init__(self, api_key: str | None = None):
        """Initialize Gemini Deep Research client"""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")
        
        # Initialize the client
        self.client = genai.Client(api_key=self.api_key)
        
        # Model for deep research
        self.model_id = "gemini-2.0-flash-exp"  # Latest with grounding
    
    async def research_topic(
        self,
        topic: str,
        context: str = "",
        max_wait_seconds: int = 300  # 5 minutes max
    ) -> Dict:
        """
        Perform deep research on a topic using Gemini
        
        Args:
            topic: The topic to research
            context: Additional context about the podcast/audience
            max_wait_seconds: Maximum time to wait for research completion
        
        Returns:
            {
                "summary": "AI-generated summary",
                "key_facts": ["fact1", "fact2", ...],
                "sources": [{"title": "...", "url": "..."}],
                "search_queries": ["query1", "query2", ...],
                "report": "Full research report markdown"
            }
        """
        
        # Construct research prompt
        prompt = self._build_research_prompt(topic, context)
        
        # Start deep research interaction (async/background)
        print(f"🔍 Starting deep research on: {topic}")
        
        interaction = await self._start_deep_research(prompt)
        
        # Poll for completion
        result = await self._wait_for_completion(
            interaction_id=interaction.id,
            max_wait_seconds=max_wait_seconds
        )
        
        # Parse and structure the results
        structured_result = self._parse_research_results(result)
        
        return structured_result
    
    def _build_research_prompt(self, topic: str, context: str) -> str:
        """Build optimized prompt for deep research"""
        
        prompt = f"""Research this topic comprehensively for a podcast episode:

Topic: {topic}

{f'Context: {context}' if context else ''}

Please provide:
1. A concise executive summary (2-3 sentences)
2. 5-7 key facts that would be interesting for a podcast discussion
3. Any recent developments or controversies
4. Expert opinions or quotes (if available)
5. Common misconceptions about this topic
6. Potential counterarguments or different perspectives

Structure your report with clear sections.
Include citations for all factual claims.
Focus on information from the last 30 days when possible.
"""
        return prompt
    
    async def _start_deep_research(self, prompt: str) -> types.Interaction:
        """Start deep research interaction"""
        
        # Configure grounding with Google Search
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_modalities=["TEXT"]
        )
        
        # Start interaction in background mode
        interaction = self.client.interactions.create(
            model=self.model_id,
            config=config,
            background=True  # Long-running research
        )
        
        # Send research request
        interaction = self.client.interactions.send_message(
            id=interaction.id,
            contents=[types.Content(parts=[types.Part(text=prompt)])]
        )
        
        return interaction
    
    async def _wait_for_completion(
        self,
        interaction_id: str,
        max_wait_seconds: int = 300,
        poll_interval: int = 5
    ) -> types.Interaction:
        """Poll interaction until completion"""
        
        start_time = time.time()
        
        while True:
            # Check if timeout exceeded
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                raise TimeoutError(
                    f"Deep research exceeded {max_wait_seconds}s timeout"
                )
            
            # Get current interaction state
            interaction = self.client.interactions.get(id=interaction_id)
            
            # Check status
            if interaction.status == "completed":
                print(f"✅ Research completed in {elapsed:.1f}s")
                return interaction
            
            elif interaction.status == "failed":
                error_msg = interaction.error or "Unknown error"
                raise Exception(f"Deep research failed: {error_msg}")
            
            elif interaction.status == "in_progress":
                print(f"⏳ Research in progress... ({elapsed:.0f}s)")
                await asyncio.sleep(poll_interval)
            
            else:
                raise Exception(f"Unexpected status: {interaction.status}")
    
    def _parse_research_results(self, interaction: types.Interaction) -> Dict:
        """Parse Gemini research results into structured format"""
        
        # Extract the response text
        if not interaction.messages or len(interaction.messages) == 0:
            raise Exception("No research results returned")
        
        # Get the last message (research report)
        last_message = interaction.messages[-1]
        report_text = last_message.content.parts[0].text if last_message.content.parts else ""
        
        # Extract grounding metadata
        grounding_metadata = getattr(last_message, 'grounding_metadata', None)
        
        sources = []
        search_queries = []
        
        if grounding_metadata:
            # Extract sources
            if hasattr(grounding_metadata, 'grounding_chunks'):
                for chunk in grounding_metadata.grounding_chunks:
                    if hasattr(chunk, 'web'):
                        sources.append({
                            "title": chunk.web.title,
                            "url": chunk.web.uri
                        })
            
            # Extract search queries used
            if hasattr(grounding_metadata, 'web_search_queries'):
                search_queries = list(grounding_metadata.web_search_queries)
        
        # Parse key facts from the report
        key_facts = self._extract_key_facts(report_text)
        
        # Generate summary (first paragraph usually)
        summary = self._extract_summary(report_text)
        
        return {
            "summary": summary,
            "key_facts": key_facts,
            "sources": sources,
            "search_queries": search_queries,
            "report": report_text,
            "metadata": {
                "word_count": len(report_text.split()),
                "source_count": len(sources),
                "query_count": len(search_queries)
            }
        }
    
    def _extract_summary(self, report: str) -> str:
        """Extract summary from research report"""
        # Simple heuristic: first paragraph or first 200 words
        paragraphs = report.split('\n\n')
        if paragraphs:
            return paragraphs[0][:500]  # First 500 chars
        return report[:200]
    
    def _extract_key_facts(self, report: str, max_facts: int = 7) -> List[str]:
        """Extract key facts from the report"""
        facts = []
        
        # Look for numbered lists or bullet points
        lines = report.split('\n')
        for line in lines:
            line = line.strip()
            # Match bullet points or numbered lists
            if line.startswith(('- ', '* ', '• ')) or (
                len(line) > 2 and line[0].isdigit() and line[1] in '.)'
            ):
                # Remove the bullet/number
                fact = line.lstrip('0123456789-*•. )')
                if fact and len(fact) > 20:  # Meaningful facts only
                    facts.append(fact)
        
        return facts[:max_facts]
    
    async def research_multiple_topics(
        self,
        topics: List[str],
        context: str = "",
        max_concurrent: int = 3
    ) -> List[Dict]:
        """
        Research multiple topics in parallel
        
        Args:
            topics: List of topics to research
            context: Common context for all topics
            max_concurrent: Max parallel research tasks
        
        Returns:
            List of research results for each topic
        """
        
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def research_one(topic: str):
            async with semaphore:
                return await self.research_topic(topic, context)
        
        # Research all topics in parallel (with limit)
        tasks = [research_one(topic) for topic in topics]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out any errors
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Failed to research '{topics[i]}': {result}")
            else:
                successful_results.append(result)
        
        return successful_results


# Integration with your existing research engine
class EnhancedResearchEngine:
    """
    Enhanced research engine using Gemini Deep Research
    Replaces manual RSS/Reddit scraping with autonomous AI research
    """
    
    def __init__(self):
        self.deep_research = GeminiDeepResearch()
        # Keep your existing sources as fallback
        from src.intelligence.research.content_sources import ContentSourceManager
        self.source_manager = ContentSourceManager()
    
    async def deep_dive(
        self,
        profile_id: int,
        topic_count: int = 5
    ) -> Dict:
        """
        Perform deep research for podcast episode
        
        Returns research bundle compatible with your existing pipeline
        """
        
        # Get profile settings
        from webapp.models import PodcastProfile
        from webapp.app import get_db
        
        db = get_db()
        profile = db.query(PodcastProfile).get(profile_id)
        
        # Step 1: Get trending topics from your sources
        print("📡 Fetching trending topics from sources...")
        trending = await self.source_manager.fetch_trending_topics(
            profile_id=profile_id,
            limit=topic_count * 2  # Get 2x, we'll filter
        )
        
        # Step 2: Use Gemini Deep Research on each topic
        print(f"🔬 Deep researching {len(trending)} topics...")
        
        context = f"""
        Podcast: {profile.name}
        Target Audience: {profile.target_audience}
        Tone: {profile.tone}
        """
        
        research_results = await self.deep_research.research_multiple_topics(
            topics=[t["title"] for t in trending[:topic_count]],
            context=context,
            max_concurrent=2  # Don't overwhelm API
        )
        
        # Step 3: Structure into your existing format
        research_bundle = {
            "profile_id": profile_id,
            "generated_at": datetime.utcnow().isoformat(),
            "topics": []
        }
        
        for i, result in enumerate(research_results):
            topic_data = {
                "title": trending[i]["title"],
                "summary": result["summary"],
                "key_facts": result["key_facts"],
                "sources": result["sources"],
                "search_queries": result["search_queries"],
                "report": result["report"],
                "metadata": {
                    **result["metadata"],
                    "original_source": trending[i].get("source", "unknown")
                }
            }
            research_bundle["topics"].append(topic_data)
        
        # Save to your existing research file format
        await self._save_research_bundle(profile_id, research_bundle)
        
        return research_bundle
    
    async def _save_research_bundle(self, profile_id: int, bundle: Dict):
        """Save research bundle to output/scripts/{episode_id}_research.json"""
        import json
        from pathlib import Path
        
        # Generate episode ID
        episode_id = f"ep_{profile_id}_{int(time.time())}"
        
        output_path = Path("output/scripts") / f"{episode_id}_research.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(bundle, f, indent=2)
        
        print(f"💾 Saved research bundle to {output_path}")


# Example usage
async def test_deep_research():
    """Test the Gemini Deep Research integration"""
    
    researcher = GeminiDeepResearch()
    
    # Research a single topic
    result = await researcher.research_topic(
        topic="H1B visa cap reached for 2025",
        context="Tech-focused immigration podcast for Indian professionals"
    )
    
    print("\n" + "="*60)
    print("RESEARCH RESULTS")
    print("="*60)
    print(f"\nSummary: {result['summary']}")
    print(f"\nKey Facts:")
    for i, fact in enumerate(result['key_facts'], 1):
        print(f"  {i}. {fact}")
    
    print(f"\nSources ({len(result['sources'])}):")
    for source in result['sources'][:5]:  # Show first 5
        print(f"  • {source['title']}")
        print(f"    {source['url']}")
    
    print(f"\nSearch Queries Used:")
    for query in result['search_queries']:
        print(f"  • {query}")
    
    print(f"\nFull Report:\n{result['report'][:500]}...")


if __name__ == "__main__":
    # Test it
    asyncio.run(test_deep_research())
