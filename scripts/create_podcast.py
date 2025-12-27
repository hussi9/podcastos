#!/usr/bin/env python3
"""
Universal Podcast Creator CLI
Create a new podcast profile for ANY topic in minutes!

Usage:
    python scripts/create_podcast.py
    python scripts/create_podcast.py --template tech
    python scripts/create_podcast.py --custom
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.universal_podcast_config import (
    ConfigTemplates, ConfigManager, UniversalPodcastConfig,
    PodcastType, ToneStyle, AudienceType
)


class PodcastCreatorCLI:
    """Interactive CLI for creating podcast profiles"""
    
    TEMPLATES = {
        "1": ("tech", "Tech & Startups"),
        "2": ("gaming", "Gaming & Esports"),
        "3": ("business", "Business & Finance"),
        "4": ("sports", "Sports"),
        "5": ("science", "Science & Education"),
        "6": ("entertainment", "Entertainment & Pop Culture"),
        "7": ("health", "Health & Fitness"),
        "8": ("food", "Food & Cooking"),
        "9": ("travel", "Travel & Lifestyle"),
        "10": ("news", "Daily News"),
        "11": ("custom", "Custom (Your Own Topic)")
    }
    
    def run_interactive(self):
        """Run interactive podcast creator"""
        
        print("\n" + "="*70)
        print("🎙️  UNIVERSAL AI PODCAST CREATOR")
        print("="*70)
        print("\nCreate professional AI-powered podcasts for ANY topic!\n")
        
        # Step 1: Choose template or custom
        print("📋 STEP 1: Choose Your Podcast Type\n")
        for key, (_, name) in self.TEMPLATES.items():
            print(f"  {key}. {name}")
        
        choice = input("\nEnter your choice (1-11): ").strip()
        
        if choice not in self.TEMPLATES:
            print("❌ Invalid choice!")
            return
        
        template_key, template_name = self.TEMPLATES[choice]
        
        if template_key == "custom":
            config = self._create_custom()
        else:
            config = self._create_from_template(template_key, template_name)
        
        if config:
            # Save configuration
            self._save_config(config)
            print("\n✅ Podcast created successfully!")
            print(f"\n📁 Configuration saved to: config/profiles/{config.name.lower().replace(' ', '_')}.yaml")
            print(f"\n🚀 Next steps:")
            print(f"   1. Review your config: config/profiles/{config.name.lower().replace(' ', '_')}.yaml")
            print(f"   2. Test generation: python scripts/test_podcast.py --profile {config.name}")
            print(f"   3. Go live: Follow MIGRATION_CHECKLIST.md")
    
    def _create_from_template(self, template_key: str, template_name: str):
        """Create podcast from built-in template"""
        
        print(f"\n✨ Creating {template_name} podcast...\n")
        
        # Get base template
        if template_key == "tech":
            config = ConfigTemplates.tech_startups()
        elif template_key == "gaming":
            config = ConfigTemplates.gaming()
        elif template_key == "business":
            config = ConfigTemplates.business_finance()
        elif template_key == "sports":
            config = ConfigTemplates.sports()
        elif template_key == "science":
            config = ConfigTemplates.science()
        else:
            config = ConfigTemplates.tech_startups()  # Default
        
        # Customize basic info
        print("📝 Customize Your Podcast\n")
        
        name = input(f"Podcast name (default: {config.name}): ").strip()
        if name:
            config.name = name
        
        description = input(f"Description (default: {config.description}): ").strip()
        if description:
            config.description = description
        
        # Frequency
        print("\n⏰ Update Frequency:")
        print("  1. Daily")
        print("  2. Twice weekly")
        print("  3. Weekly")
        print("  4. Biweekly")
        print("  5. Monthly")
        
        freq_choice = input("Choose (1-5, default: 3): ").strip() or "3"
        freq_map = {
            "1": "daily",
            "2": "twice_weekly",
            "3": "weekly",
            "4": "biweekly",
            "5": "monthly"
        }
        config.production.update_frequency = freq_map.get(freq_choice, "weekly")
        
        # Length
        length = input(f"\nTarget length in minutes (default: {config.production.target_length_minutes}): ").strip()
        if length and length.isdigit():
            config.production.target_length_minutes = int(length)
        
        return config
    
    def _create_custom(self):
        """Create fully custom podcast"""
        
        print("\n🎨 Create Custom Podcast\n")
        
        # Basic info
        name = input("Podcast name: ").strip()
        if not name:
            print("❌ Name is required!")
            return None
        
        description = input("Brief description: ").strip() or f"A podcast about {name}"
        
        # Topics
        print("\nTopics (comma-separated, e.g., 'ai, startups, tech'):")
        topics_input = input("Topics: ").strip()
        topics = [t.strip() for t in topics_input.split(",") if t.strip()]
        
        if not topics:
            print("❌ At least one topic is required!")
            return None
        
        # Keywords
        print("\n🔑 Keywords for Content Filtering")
        print("(These help find relevant content from sources)")
        keywords_input = input("Keywords (comma-separated): ").strip()
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        
        # Sources
        print("\n📡 Content Sources")
        print("(We'll ask for each platform)")
        
        sources = {}
        
        # Reddit
        reddit_input = input("\nReddit subreddits (comma-separated, e.g., 'tech,programming'): ").strip()
        if reddit_input:
            sources["reddit"] = [s.strip() for s in reddit_input.split(",")]
        
        # Twitter
        twitter_input = input("Twitter accounts (comma-separated, e.g., 'techcrunch,verge'): ").strip()
        if twitter_input:
            sources["twitter"] = [s.strip() for s in twitter_input.split(",")]
        
        # RSS
        rss_input = input("RSS feed URLs (comma-separated): ").strip()
        if rss_input:
            sources["rss"] = [s.strip() for s in rss_input.split(",")]
        
        # YouTube
        youtube_input = input("YouTube channel IDs (comma-separated, optional): ").strip()
        if youtube_input:
            sources["youtube"] = [s.strip() for s in youtube_input.split(",")]
        
        if not any(sources.values()):
            print("❌ At least one content source is required!")
            return None
        
        # Production settings
        print("\n🎬 Production Settings")
        
        length = input("Target length in minutes (default: 20): ").strip()
        target_length = int(length) if length.isdigit() else 20
        
        print("\n⏰ Update Frequency:")
        print("  1. Daily  2. Twice weekly  3. Weekly  4. Biweekly  5. Monthly")
        freq_choice = input("Choose (default: 3): ").strip() or "3"
        freq_map = {"1": "daily", "2": "twice_weekly", "3": "weekly", "4": "biweekly", "5": "monthly"}
        frequency = freq_map.get(freq_choice, "weekly")
        
        print("\n🎭 Tone Style:")
        print("  1. Professional  2. Casual  3. Enthusiastic  4. Educational")
        tone_choice = input("Choose (default: 2): ").strip() or "2"
        tone_map = {
            "1": ToneStyle.PROFESSIONAL_NEUTRAL,
            "2": ToneStyle.CASUAL_CONVERSATIONAL,
            "3": ToneStyle.ENTHUSIASTIC_ENERGETIC,
            "4": ToneStyle.EDUCATIONAL_ACCESSIBLE
        }
        tone = tone_map.get(tone_choice, ToneStyle.CASUAL_CONVERSATIONAL)
        
        print("\n👥 Target Audience:")
        print("  1. General public  2. Professionals  3. Enthusiasts  4. Beginners  5. Experts")
        audience_choice = input("Choose (default: 1): ").strip() or "1"
        audience_map = {
            "1": AudienceType.GENERAL_PUBLIC,
            "2": AudienceType.PROFESSIONALS,
            "3": AudienceType.ENTHUSIASTS,
            "4": AudienceType.BEGINNERS,
            "5": AudienceType.EXPERTS
        }
        audience = audience_map.get(audience_choice, AudienceType.GENERAL_PUBLIC)
        
        # Create config
        from src.config.universal_podcast_config import (
            SourceConfig, AIConfig, ProductionConfig
        )
        
        config = UniversalPodcastConfig(
            name=name,
            description=description,
            podcast_type=PodcastType.CUSTOM,
            topics=topics,
            required_keywords=keywords,
            sources=SourceConfig(
                subreddits=sources.get("reddit", []),
                twitter_accounts=sources.get("twitter", []),
                rss_feeds=[{"url": url, "name": url} for url in sources.get("rss", [])],
                youtube_channels=sources.get("youtube", [])
            ),
            ai=AIConfig(
                tone=tone,
                audience=audience
            ),
            production=ProductionConfig(
                target_length_minutes=target_length,
                update_frequency=frequency
            )
        )
        
        return config
    
    def _save_config(self, config: UniversalPodcastConfig):
        """Save configuration to file"""
        
        # Create profiles directory
        profiles_dir = Path("config/profiles")
        profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = config.name.lower().replace(" ", "_").replace("-", "_")
        filepath = profiles_dir / f"{filename}.yaml"
        
        # Save
        ConfigManager.save_config(config, str(filepath))
        
        # Also save as JSON for easy reading
        import json
        from dataclasses import asdict
        
        config_dict = asdict(config)
        # Convert enums
        config_dict['podcast_type'] = config.podcast_type.value
        config_dict['ai']['tone'] = config.ai.tone.value
        config_dict['ai']['audience'] = config.ai.audience.value
        
        json_filepath = profiles_dir / f"{filename}.json"
        with open(json_filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Create a new podcast profile for ANY topic"
    )
    parser.add_argument(
        "--template",
        choices=["tech", "gaming", "business", "sports", "science", "entertainment"],
        help="Use a built-in template"
    )
    parser.add_argument(
        "--custom",
        action="store_true",
        help="Create custom podcast interactively"
    )
    
    args = parser.parse_args()
    
    cli = PodcastCreatorCLI()
    
    if args.template:
        # Quick create from template
        template_map = {
            "tech": ConfigTemplates.tech_startups,
            "gaming": ConfigTemplates.gaming,
            "business": ConfigTemplates.business_finance,
            "sports": ConfigTemplates.sports,
            "science": ConfigTemplates.science
        }
        
        config = template_map[args.template]()
        cli._save_config(config)
        print(f"✅ Created {config.name} podcast from template!")
    
    elif args.custom:
        config = cli._create_custom()
        if config:
            cli._save_config(config)
            print(f"✅ Created custom podcast: {config.name}")
    
    else:
        # Interactive mode
        cli.run_interactive()


if __name__ == "__main__":
    main()
