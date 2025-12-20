"""Exa.ai researcher for counter-arguments and balanced perspectives."""

import os
from typing import Optional
import logging

from exa_py import Exa

from ..models.research import CounterArgument, ExpertOpinion


logger = logging.getLogger(__name__)


class ExaResearcher:
    """
    Exa.ai researcher for finding counter-arguments and alternative perspectives.

    Why Exa?
    - 94.9% accuracy on SimpleQA benchmark (vs Google's SEO-biased results)
    - Neural/semantic search (understands meaning, not just keywords)
    - Great for finding authoritative counter-arguments
    - Overcomes Google's bias toward SEO-optimized content
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        self._client: Optional[Exa] = None

    @property
    def client(self) -> Exa:
        """Lazy load the Exa client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("EXA_API_KEY not set")
            self._client = Exa(api_key=self.api_key)
        return self._client

    async def find_counter_arguments(
        self,
        topic: str,
        main_claim: str,
        num_results: int = 5,
    ) -> list[CounterArgument]:
        """
        Find counter-arguments to a main claim.
        Uses semantic search to find opposing viewpoints.
        """
        counter_args = []

        # Search for opposing views
        queries = [
            f"criticism of {topic}",
            f"problems with {topic}",
            f"why {topic} is wrong",
            f"alternative to {topic}",
            f"downside of {topic}",
        ]

        for query in queries[:3]:  # Limit API calls
            try:
                results = self.client.search_and_contents(
                    query,
                    type="neural",
                    num_results=num_results,
                    text=True,
                    highlights=True,
                )

                for result in results.results:
                    # Extract the most relevant highlight
                    highlight = ""
                    if result.highlights:
                        highlight = result.highlights[0] if result.highlights else ""

                    counter_args.append(
                        CounterArgument(
                            argument=highlight or result.text[:500],
                            source_url=result.url,
                            source_name=self._extract_domain(result.url),
                            source_credibility=self._estimate_credibility(result.url),
                            context=result.title,
                        )
                    )

            except Exception as e:
                logger.error(f"Exa search error for '{query}': {e}")

        # Deduplicate by URL
        seen_urls = set()
        unique_args = []
        for arg in counter_args:
            if arg.source_url not in seen_urls:
                seen_urls.add(arg.source_url)
                unique_args.append(arg)

        logger.info(f"Found {len(unique_args)} counter-arguments for '{topic}'")
        return unique_args[:num_results]

    async def find_expert_opinions(
        self,
        topic: str,
        num_results: int = 5,
    ) -> list[ExpertOpinion]:
        """
        Find expert opinions on a topic.
        """
        experts = []

        queries = [
            f"expert opinion on {topic}",
            f"professor {topic} research",
            f"analyst view on {topic}",
        ]

        for query in queries[:2]:
            try:
                results = self.client.search_and_contents(
                    query,
                    type="neural",
                    num_results=num_results,
                    text=True,
                    highlights=True,
                )

                for result in results.results:
                    highlight = result.highlights[0] if result.highlights else result.text[:500]

                    # Try to extract expert name from title/text
                    expert_name = self._extract_expert_name(result.title, highlight)

                    if expert_name:
                        experts.append(
                            ExpertOpinion(
                                quote=highlight,
                                expert_name=expert_name,
                                source_url=result.url,
                                relevance_score=result.score if hasattr(result, 'score') else 0.7,
                            )
                        )

            except Exception as e:
                logger.error(f"Exa expert search error for '{query}': {e}")

        return experts[:num_results]

    async def find_similar_content(
        self,
        url: str,
        num_results: int = 5,
    ) -> list[dict]:
        """
        Find content similar to a given URL.
        Useful for finding additional sources on the same topic.
        """
        try:
            results = self.client.find_similar_and_contents(
                url,
                num_results=num_results,
                text=True,
            )

            return [
                {
                    "title": r.title,
                    "url": r.url,
                    "text": r.text[:500] if r.text else "",
                }
                for r in results.results
            ]

        except Exception as e:
            logger.error(f"Exa similar search error: {e}")
            return []

    async def research_balanced_view(
        self,
        topic: str,
        initial_stance: str = "neutral",
    ) -> dict:
        """
        Research a topic from multiple angles for balanced coverage.
        """
        result = {
            "pro_arguments": [],
            "con_arguments": [],
            "expert_opinions": [],
            "additional_sources": [],
        }

        # Pro arguments
        try:
            pro_results = self.client.search_and_contents(
                f"benefits of {topic} advantages",
                type="neural",
                num_results=3,
                text=True,
                highlights=True,
            )
            for r in pro_results.results:
                result["pro_arguments"].append({
                    "argument": r.highlights[0] if r.highlights else r.text[:300],
                    "source": r.url,
                })
        except Exception as e:
            logger.error(f"Exa pro search error: {e}")

        # Con arguments
        try:
            con_results = self.client.search_and_contents(
                f"problems with {topic} disadvantages criticism",
                type="neural",
                num_results=3,
                text=True,
                highlights=True,
            )
            for r in con_results.results:
                result["con_arguments"].append({
                    "argument": r.highlights[0] if r.highlights else r.text[:300],
                    "source": r.url,
                })
        except Exception as e:
            logger.error(f"Exa con search error: {e}")

        # Expert opinions
        result["expert_opinions"] = await self.find_expert_opinions(topic, 3)

        return result

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return url

    def _estimate_credibility(self, url: str) -> float:
        """Estimate source credibility based on domain."""
        domain = self._extract_domain(url).lower()

        # High credibility domains
        high_cred = [
            "reuters.com", "bbc.com", "nytimes.com", "wsj.com",
            "nature.com", "science.org", "edu", "gov",
            "arstechnica.com", "theatlantic.com", "economist.com",
        ]

        # Medium credibility
        medium_cred = [
            "techcrunch.com", "theverge.com", "wired.com",
            "bloomberg.com", "forbes.com",
        ]

        for d in high_cred:
            if d in domain:
                return 0.9

        for d in medium_cred:
            if d in domain:
                return 0.75

        # Check for academic/government
        if ".edu" in domain or ".gov" in domain:
            return 0.95

        return 0.6  # Default

    def _extract_expert_name(self, title: str, text: str) -> Optional[str]:
        """Try to extract an expert name from content."""
        import re

        combined = f"{title} {text}"

        # Patterns for expert names
        patterns = [
            r'(?:Dr\.|Professor|Prof\.) ([A-Z][a-z]+ [A-Z][a-z]+)',
            r'([A-Z][a-z]+ [A-Z][a-z]+), (?:PhD|MD|professor|analyst)',
            r'(?:according to|says|said) ([A-Z][a-z]+ [A-Z][a-z]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, combined)
            if match:
                return match.group(1)

        return None
