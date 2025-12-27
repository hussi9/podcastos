"""
Enhanced Newsletter Generator using Gemini 2.0 Flash Thinking
Combines: ADK agents + Deep Research + Thinking mode for premium quality
"""
import os
import json
from typing import Dict, List
from datetime import datetime
from google import genai
from google.genai import types


class GeminiThinkingNewsletterGenerator:
    """
    Premium newsletter generator using Gemini 2.0 Flash Thinking
    (Nano Banana Pro - shows reasoning process for better analysis)
    """
    
    def __init__(self, api_key: str | None = None):
        """Initialize with Gemini 2.0 Flash Thinking"""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required")
        
        # Initialize client
        self.client = genai.Client(api_key=self.api_key)
        
        # Use Gemini 2.0 Flash Thinking for analytical content
        self.thinking_model = "gemini-2.0-flash-thinking-exp"
        self.flash_model = "gemini-2.0-flash-exp"
    
    async def generate_newsletter(
        self,
        research_bundle: Dict,
        profile_settings: Dict
    ) -> Dict:
        """
        Generate premium newsletter from research
        
        Args:
            research_bundle: Deep research results
            profile_settings: Podcast profile (audience, tone, etc.)
        
        Returns:
            {
                "title": "...",
                "subtitle": "...",
                "intro": "...",
                "sections": [...],
                "outro": "...",
                "content_markdown": "...",
                "content_html": "...",
                "metadata": {...}
            }
        """
        
        print("📝 Generating newsletter with Gemini 2.0 Flash Thinking...")
        
        # Step 1: Generate newsletter structure + intro (with thinking)
        structure = await self._generate_structure_with_thinking(
            research_bundle, profile_settings
        )
        
        # Step 2: Generate each section (with deep analysis)
        sections = []
        for i, topic in enumerate(research_bundle["topics"], 1):
            print(f"  ✍️  Section {i}/{len(research_bundle['topics'])}: {topic['title']}")
            section = await self._generate_section_with_thinking(
                topic, profile_settings, i
            )
            sections.append(section)
        
        # Step 3: Generate outro (with thinking)
        outro = await self._generate_outro_with_thinking(
            research_bundle, profile_settings
        )
        
        # Step 4: Assemble complete newsletter
        newsletter = {
            "title": structure["title"],
            "subtitle": structure["subtitle"],
            "intro": structure["intro"],
            "sections": sections,
            "outro": outro,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "model": self.thinking_model,
                "topic_count": len(sections),
                "total_words": self._count_words(structure, sections, outro),
                "audience": profile_settings.get("target_audience", "general"),
                "tone": profile_settings.get("tone", "conversational")
            }
        }
        
        # Convert to markdown and HTML
        newsletter["content_markdown"] = self._to_markdown(newsletter)
        newsletter["content_html"] = self._to_html(newsletter)
        
        return newsletter
    
    async def _generate_structure_with_thinking(
        self,
        research_bundle: Dict,
        profile_settings: Dict
    ) -> Dict:
        """Generate newsletter title, subtitle, and intro with reasoning"""
        
        prompt = f"""You are a premium newsletter editor for: {profile_settings['name']}

TARGET AUDIENCE: {profile_settings.get('target_audience', 'General audience')}
TONE: {profile_settings.get('tone', 'Conversational and insightful')}

RESEARCH TOPICS:
{json.dumps([t['title'] for t in research_bundle['topics']], indent=2)}

YOUR TASK:
1. **Think deeply** about what ties these topics together
2. Create a compelling newsletter title (creative, not generic)
3. Write a subtitle that hooks the reader
4. Craft an intro paragraph (2-3 sentences) that:
   - Sets the scene
   - Creates intrigue
   - Previews the insights to come

IMPORTANT: This is for a premium audience. Be analytical, not clickbait-y.

Return ONLY a JSON object:
{{
    "title": "...",
    "subtitle": "...",
    "intro": "..."
}}"""

        response = await self.client.aio.models.generate_content(
            model=self.thinking_model,  # Uses thinking mode!
            contents=prompt
        )
        
        # Parse JSON response
        result_text = response.text
        
        # Extract JSON (strip markdown fences if present)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    
    async def _generate_section_with_thinking(
        self,
        topic: Dict,
        profile_settings: Dict,
        section_number: int
    ) -> Dict:
        """Generate newsletter section with deep analysis"""
        
        prompt = f"""You are writing Section {section_number} of a premium newsletter.

TOPIC: {topic['title']}

RESEARCH:
Summary: {topic['summary']}

Key Facts:
{chr(10).join(f"- {fact}" for fact in topic['key_facts'])}

Sources: {len(topic.get('sources', []))} verified sources

TARGET AUDIENCE: {profile_settings.get('target_audience')}
TONE: {profile_settings.get('tone')}

YOUR TASK - Write this section using a 4-part narrative structure:

1. **HOOK** (1 sentence)
   - Start with something surprising, counterintuitive, or timely
   - Make them want to keep reading

2. **ANALYSIS** (2-3 sentences)
   - Go beyond the surface facts
   - Explain WHY this matters
   - Connect dots others miss

3. **EXPERT VIEW** (1-2 sentences)
   - Include a quote, data point, or expert perspective
   - Add credibility and depth

4. **TAKEAWAY** (1 sentence)
   - What should the reader actually DO with this info?
   - Make it actionable or thought-provoking

IMPORTANT:
- Write like a Substack editor (analytical, not news reporter)
- Use "you" to make it personal
- NO generic phrases like "in today's world" or "it's important to note"
- Be specific with data/facts from the research

Return ONLY JSON:
{{
    "heading": "Compelling section title",
    "content": "Full section text with all 4 parts..."
}}"""

        response = await self.client.aio.models.generate_content(
            model=self.thinking_model,  # Deep thinking for quality
            contents=prompt
        )
        
        # Parse response
        result_text = response.text
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        section_data = json.loads(result_text.strip())
        
        # Add sources
        section_data["sources"] = topic.get("sources", [])[:3]  # Top 3 sources
        
        return section_data
    
    async def _generate_outro_with_thinking(
        self,
        research_bundle: Dict,
        profile_settings: Dict
    ) -> str:
        """Generate newsletter outro with thinking"""
        
        topics_summary = ", ".join([t['title'] for t in research_bundle['topics']])
        
        prompt = f"""Write a newsletter outro paragraph.

TOPICS COVERED: {topics_summary}

TARGET AUDIENCE: {profile_settings.get('target_audience')}
TONE: {profile_settings.get('tone')}

YOUR TASK:
Write a 2-3 sentence outro that:
1. Ties the topics together (what's the common thread?)
2. Leaves them with a thought-provoking question or insight
3. Feels personal (conversational, not formal)

STYLE: Like a friend sharing insights over coffee, not a professor lecturing.

Return ONLY the outro text (no JSON, just the paragraph)."""

        response = await self.client.aio.models.generate_content(
            model=self.thinking_model,
            contents=prompt
        )
        
        return response.text.strip()
    
    def _to_markdown(self, newsletter: Dict) -> str:
        """Convert newsletter to markdown format"""
        
        md = f"# {newsletter['title']}\n\n"
        md += f"*{newsletter['subtitle']}*\n\n"
        md += f"{newsletter['intro']}\n\n"
        md += "---\n\n"
        
        for i, section in enumerate(newsletter['sections'], 1):
            md += f"## {section['heading']}\n\n"
            md += f"{section['content']}\n\n"
            
            # Add sources if available
            if section.get('sources'):
                md += "*Sources:*\n"
                for source in section['sources']:
                    md += f"- [{source['title']}]({source['url']})\n"
                md += "\n"
        
        md += "---\n\n"
        md += f"{newsletter['outro']}\n"
        
        return md
    
    def _to_html(self, newsletter: Dict) -> str:
        """Convert newsletter to HTML format"""
        
        html = f"""<article class="newsletter">
    <header>
        <h1>{newsletter['title']}</h1>
        <p class="subtitle">{newsletter['subtitle']}</p>
    </header>
    
    <div class="intro">
        <p>{newsletter['intro']}</p>
    </div>
    
    <div class="sections">
"""
        
        for section in newsletter['sections']:
            html += f"""        <section>
            <h2>{section['heading']}</h2>
            <div class="content">
                {self._paragraphs_to_html(section['content'])}
            </div>
"""
            if section.get('sources'):
                html += '            <div class="sources">\n'
                html += '                <p class="sources-label">Sources:</p>\n'
                html += '                <ul>\n'
                for source in section['sources']:
                    html += f'                    <li><a href="{source["url"]}" target="_blank">{source["title"]}</a></li>\n'
                html += '                </ul>\n'
                html += '            </div>\n'
            
            html += '        </section>\n\n'
        
        html += f"""    </div>
    
    <footer class="outro">
        <p>{newsletter['outro']}</p>
    </footer>
</article>"""
        
        return html
    
    def _paragraphs_to_html(self, text: str) -> str:
        """Convert plain text paragraphs to HTML"""
        paragraphs = text.split('\n\n')
        return '\n'.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())
    
    def _count_words(self, structure: Dict, sections: List[Dict], outro: str) -> int:
        """Count total words in newsletter"""
        total = 0
        total += len(structure['intro'].split())
        for section in sections:
            total += len(section['content'].split())
        total += len(outro.split())
        return total


# Integration with your existing pipeline
async def generate_newsletter_from_research(
    research_bundle: Dict,
    profile_settings: Dict,
    save_path: str | None = None
) -> Dict:
    """
    Standalone function to generate newsletter
    
    Usage:
        newsletter = await generate_newsletter_from_research(
            research_bundle=deep_research_results,
            profile_settings=profile.to_dict()
        )
    """
    
    generator = GeminiThinkingNewsletterGenerator()
    newsletter = await generator.generate_newsletter(
        research_bundle=research_bundle,
        profile_settings=profile_settings
    )
    
    # Optionally save to file
    if save_path:
        with open(save_path, 'w') as f:
            json.dump(newsletter, f, indent=2)
        print(f"💾 Saved newsletter to {save_path}")
    
    return newsletter


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_newsletter_generation():
        """Test newsletter generation with sample data"""
        
        # Sample research bundle (from Gemini Deep Research)
        research_bundle = {
            "topics": [
                {
                    "title": "H1B Visa Cap Reached",
                    "summary": "The H1B visa cap was reached in record time this year...",
                    "key_facts": [
                        "Cap reached in 3 days",
                        "200,000 applications received",
                        "Tech sector most affected"
                    ],
                    "sources": [
                        {"title": "USCIS Announcement", "url": "https://uscis.gov/..."}
                    ]
                },
                # ... more topics
            ]
        }
        
        profile_settings = {
            "name": "Desi Daily",
            "target_audience": "Indian professionals in tech",
            "tone": "Conversational yet analytical"
        }
        
        newsletter = await generate_newsletter_from_research(
            research_bundle=research_bundle,
            profile_settings=profile_settings
        )
        
        print("\n" + "="*60)
        print("NEWSLETTER GENERATED")
        print("="*60)
        print(f"Title: {newsletter['title']}")
        print(f"Subtitle: {newsletter['subtitle']}")
        print(f"\nTotal Words: {newsletter['metadata']['total_words']}")
        print(f"\nMarkdown Preview:\n{newsletter['content_markdown'][:500]}...")
    
    asyncio.run(test_newsletter_generation())
