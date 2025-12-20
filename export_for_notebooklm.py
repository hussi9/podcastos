#!/usr/bin/env python3
"""
Export today's trending topics for Google NotebookLM.
Creates a formatted document that can be uploaded to NotebookLM for Audio Overview generation.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


async def export_topics_for_notebooklm():
    """Gather topics and export them in NotebookLM-friendly format."""

    from src.aggregators import ContentRanker
    from src.research import TopicResearcher

    print("🔍 Gathering trending topics for Desi community...")

    # Initialize aggregators
    ranker = ContentRanker(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_SERVICE_KEY"),
    )

    # Get topics
    topics = await ranker.get_ranked_topics(limit=5)
    print(f"📊 Found {len(topics)} trending topics")

    # Research topics for more depth
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        print("🔬 Deep researching each topic...")
        researcher = TopicResearcher(api_key=gemini_key)
        researched = await researcher.research_all_topics(topics)
    else:
        researched = None

    # Generate document
    today = datetime.now()
    date_str = today.strftime("%B %d, %Y")

    output = []
    output.append(f"# Desi Daily Podcast - {date_str}")
    output.append("")
    output.append("## About This Podcast")
    output.append("Desi Daily is a news and discussion podcast for the South Asian immigrant community in the United States. Two hosts, Raj and Priya, discuss trending topics that affect desi immigrants - from visa updates to career news to cultural topics.")
    output.append("")
    output.append("## Hosts")
    output.append("- **Raj**: An immigrant who came to the US 12 years ago on an H-1B visa, now a green card holder working in tech. He provides practical advice based on his experience navigating the immigration system.")
    output.append("- **Priya**: A second-generation Indian-American whose parents immigrated in the 1980s. She brings community perspectives and emotional intelligence to discussions.")
    output.append("")
    output.append("---")
    output.append("")
    output.append("# Today's Topics")
    output.append("")

    for i, topic in enumerate(topics, 1):
        output.append(f"## Topic {i}: {topic.title}")
        output.append(f"**Category**: {topic.category}")

        if topic.is_breaking:
            output.append("**Status**: 🔴 BREAKING NEWS")
        elif topic.is_trending:
            output.append("**Status**: 📈 TRENDING")

        output.append("")

        if topic.summary:
            output.append(f"**Summary**: {topic.summary}")
            output.append("")

        if topic.key_points:
            output.append("**Key Points**:")
            for point in topic.key_points:
                output.append(f"- {point}")
            output.append("")

        if topic.sources:
            output.append(f"**Sources**: {', '.join(topic.sources)}")
            output.append("")

        # Add research if available
        if researched and i <= len(researched):
            research = researched[i-1]

            if research.key_facts:
                output.append("**Key Facts**:")
                for fact in research.key_facts:
                    source = f" ({fact.source})" if fact.source else ""
                    output.append(f"- {fact.fact}{source}")
                output.append("")

            if research.statistics:
                output.append("**Statistics**:")
                for stat in research.statistics:
                    output.append(f"- {stat}")
                output.append("")

            if research.historical_context:
                output.append("**Historical Context**:")
                output.append(research.historical_context)
                output.append("")

            if research.expert_opinions:
                output.append("**Expert Opinions**:")
                for opinion in research.expert_opinions:
                    output.append(f'- {opinion.person} ({opinion.role}): "{opinion.quote}"')
                output.append("")

            if research.practical_advice:
                output.append("**Practical Advice for Listeners**:")
                for advice in research.practical_advice:
                    output.append(f"- {advice}")
                output.append("")

        output.append("---")
        output.append("")

    # Add podcast instructions for NotebookLM
    output.append("# Podcast Generation Instructions")
    output.append("")
    output.append("## Target Audience")
    output.append("South Asian immigrants living in the United States - including H-1B workers, green card applicants, naturalized citizens, and second-generation Indian-Americans. They care deeply about immigration policy, career advancement, and staying connected to their culture while building lives in America.")
    output.append("")
    output.append("## Podcast Style Guidelines")
    output.append("When creating the Audio Overview, please follow these guidelines:")
    output.append("")
    output.append("### Conversation Flow")
    output.append("1. Start with the most urgent/breaking news topic")
    output.append("2. Group related topics together (all immigration topics, then career, then cultural)")
    output.append("3. Use clear transitions between different topic areas")
    output.append("4. End with something hopeful or forward-looking")
    output.append("")
    output.append("### Tone & Authenticity")
    output.append("1. Two hosts discussing naturally, like smart friends catching up over chai")
    output.append("2. Show genuine emotions - frustration about systemic issues, hope for positive changes")
    output.append("3. Include specific facts, statistics, and expert quotes from the research")
    output.append("4. Provide practical advice that listeners can act on")
    output.append("5. Reference the lived experience of immigrants without stereotyping")
    output.append("")
    output.append("### Things to Avoid")
    output.append("1. Do NOT use forced cultural slang like 'yaar', 'na?', 'accha' repeatedly")
    output.append("2. Do NOT make every sentence a question")
    output.append("3. Do NOT be preachy or condescending")
    output.append("4. Do NOT repeat the same facts multiple times")
    output.append("")

    # Save output
    output_dir = Path("output/notebooklm")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as Markdown
    md_path = output_dir / f"desi-daily-{today.strftime('%Y%m%d')}.md"
    with open(md_path, "w") as f:
        f.write("\n".join(output))
    print(f"📄 Saved Markdown: {md_path}")

    # Save as plain text (sometimes better for NotebookLM)
    txt_path = output_dir / f"desi-daily-{today.strftime('%Y%m%d')}.txt"
    with open(txt_path, "w") as f:
        f.write("\n".join(output))
    print(f"📄 Saved Text: {txt_path}")

    print("")
    print("=" * 60)
    print("✅ READY FOR NOTEBOOKLM!")
    print("=" * 60)
    print("")
    print("Next steps:")
    print("1. Go to: https://notebooklm.google.com")
    print("2. Create a new notebook")
    print(f"3. Upload: {md_path}")
    print("4. Click 'Audio Overview' → 'Deep Dive'")
    print("5. Wait ~2 minutes for podcast generation")
    print("6. Download the MP3!")
    print("")
    print("Optional: Use 'Deep Research' in NotebookLM to find more sources")
    print("")

    return md_path


if __name__ == "__main__":
    asyncio.run(export_topics_for_notebooklm())
