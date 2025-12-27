"""
Editorial reviewer for podcast scripts.
Refines dialogue for flow, engagement, and emotional depth.
"""

import logging
import json
import re
from typing import Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)


class EditorialReviewer:
    """
    Reviews and refines podcast scripts for:
    - Natural conversational flow
    - Emotional engagement
    - Meaningful transitions
    - Removing awkward phrasing
    """

    REVIEW_PROMPT = '''You are an expert podcast editor reviewing a script for "Desi Daily",
a news podcast for South Asian immigrants in America.

Your job is to REFINE the script for:
1. LOGICAL TOPIC FLOW - Related topics must be grouped together
2. NO REPETITION - Each topic/fact should only be discussed once
3. NATURAL TRANSITIONS - Clear but smooth moves between topics
4. EMOTIONAL DEPTH - Real feelings, not just information

CRITICAL FLOW RULES:
- Group ALL immigration topics together (H-1B, green cards, USCIS, visas)
- Group ALL career/job topics together
- Group ALL family/cultural topics together
- NEVER jump from immigration to an unrelated topic then back to immigration
- Each segment should have a CLEAR transition: "Now, shifting gears to..." or "On a related note..."
- The transition should make it OBVIOUS we're moving to a new topic

TOPIC REPETITION RULES:
- If a topic or fact was discussed in one segment, DO NOT mention it again
- Each segment should cover ONLY its designated topic
- Don't mix OECD rules into USCIS section if it's not about USCIS
- Keep tariff/trade discussions separate from immigration

CONVERSATION RULES:
- DO NOT use forced cultural slang like "yaar", "na?", "accha" repeatedly
- DO NOT make every sentence a question
- Sound like two intelligent friends who genuinely care
- Show real emotions: frustration, hope, surprise, empathy
- Keep all facts, statistics, and expert quotes

TRANSITION EXAMPLES:
GOOD: "Alright, we've covered the visa situation pretty thoroughly. Let's shift to something that affects all of us—the job market."
GOOD: "That's a lot on immigration. But speaking of careers, there's been some interesting news on tariffs..."
BAD: [Suddenly talking about tariffs in the middle of a visa discussion]
BAD: [Jumping from family topics back to immigration without transition]

EMOTIONAL TOUCHES:
- Genuine frustration: "This is what's so frustrating about this whole system..."
- Empathy: "I can only imagine how stressful that must be..."
- Hope: "But here's the thing that gives me some hope..."
- Surprise: "Wait, seriously?" or "I had no idea"

Here is the script to review and refine:

{script_json}

{episode_context}

INSTRUCTIONS:
1. First, identify any topic repetition and remove duplicates
2. Reorder segments if needed so related topics are together
3. Add clear transitions between different topic areas
4. Refine dialogue for emotional engagement
5. Ensure natural but OBVIOUS transitions between segments

Return the COMPLETE refined script in the same JSON format.
Keep all structural elements (episode_id, segments, etc.) intact.

Return ONLY valid JSON, no markdown.'''

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    async def review_script(
        self,
        script_data: dict,
        previous_episodes: list = None,
    ) -> dict:
        """
        Review and refine a podcast script.

        Args:
            script_data: The script as a dictionary
            previous_episodes: List of previous episode summaries for context

        Returns:
            Refined script data
        """
        logger.info("Starting editorial review...")

        # Build context from previous episodes
        episode_context = ""
        if previous_episodes:
            episode_context = "\nPREVIOUS EPISODE CONTEXT (for continuity):\n"
            for ep in previous_episodes[-3:]:  # Last 3 episodes
                episode_context += f"- {ep.get('date', 'Unknown')}: {ep.get('title', 'Unknown')}\n"
                if ep.get('topics'):
                    episode_context += f"  Topics covered: {', '.join(ep['topics'][:3])}\n"

        prompt = self.REVIEW_PROMPT.format(
            script_json=json.dumps(script_data, indent=2),
            episode_context=episode_context,
        )

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=15000,
                ),
            )

            refined_data = self._parse_response(response.text)

            if refined_data and "segments" in refined_data:
                logger.info("Editorial review complete")
                return refined_data
            else:
                logger.warning("Editorial review returned invalid data, using original")
                return script_data

        except Exception as e:
            logger.error(f"Editorial review failed: {e}")
            return script_data

    def _parse_response(self, response_text: str) -> dict:
        """Parse the response JSON"""
        text = response_text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in editorial review: {e}")
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Secondary JSON parse also failed in editorial review")
            return None


class EpisodeHistoryTracker:
    """
    Tracks episode history for continuity across episodes.
    Stores summaries, topics covered, and key points.
    """

    def __init__(self, history_file: str = "output/episode_history.json"):
        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self) -> list:
        """Load episode history from file"""
        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_history(self):
        """Save episode history to file"""
        import os
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def add_episode(
        self,
        episode_id: str,
        title: str,
        date: str,
        topics: list[str],
        key_facts: list[str] = None,
        summary: str = None,
    ):
        """Add an episode to history"""
        episode_entry = {
            "episode_id": episode_id,
            "title": title,
            "date": date,
            "topics": topics,
            "key_facts": key_facts or [],
            "summary": summary or "",
            "added_at": __import__("datetime").datetime.now().isoformat(),
        }

        # Check if episode already exists (update it)
        for i, ep in enumerate(self.history):
            if ep["episode_id"] == episode_id:
                self.history[i] = episode_entry
                self._save_history()
                logger.info(f"Updated episode in history: {episode_id}")
                return

        self.history.append(episode_entry)
        self._save_history()
        logger.info(f"Added episode to history: {episode_id}")

    def get_recent_episodes(self, count: int = 5) -> list:
        """Get the most recent episodes"""
        return sorted(
            self.history,
            key=lambda x: x.get("date", ""),
            reverse=True
        )[:count]

    def get_topics_covered(self, days: int = 7) -> list[str]:
        """Get all topics covered in the last N days"""
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days)
        topics = []

        for ep in self.history:
            try:
                ep_date = datetime.fromisoformat(ep.get("date", "")[:10])
                if ep_date >= cutoff:
                    topics.extend(ep.get("topics", []))
            except (ValueError, TypeError, AttributeError):
                # Skip entries with invalid date formats
                continue

        return list(set(topics))

    def check_topic_recently_covered(self, topic: str, days: int = 3) -> bool:
        """Check if a topic was covered recently"""
        recent_topics = self.get_topics_covered(days=days)
        topic_lower = topic.lower()

        for covered in recent_topics:
            if topic_lower in covered.lower() or covered.lower() in topic_lower:
                return True
        return False

    def get_continuity_context(self) -> str:
        """Generate context string for script generation"""
        recent = self.get_recent_episodes(3)

        if not recent:
            return ""

        lines = ["PREVIOUS EPISODES (for continuity - reference if relevant):"]
        for ep in recent:
            lines.append(f"\n{ep.get('date', 'Unknown date')}: {ep.get('title', 'Unknown')}")
            if ep.get('topics'):
                lines.append(f"  Topics: {', '.join(ep['topics'][:3])}")
            if ep.get('key_facts'):
                lines.append(f"  Key facts mentioned: {', '.join(ep['key_facts'][:2])}")

        return "\n".join(lines)
