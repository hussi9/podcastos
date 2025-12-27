#!/usr/bin/env python3
"""
Test Podcast Generation
Quick test to verify your configuration works

Usage:
    python scripts/test_podcast.py --profile tech_pulse
    python scripts/test_podcast.py --template tech
    python scripts/test_podcast.py --custom "My Topic"
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.universal_podcast_config import ConfigTemplates, ConfigManager
from src.intelligence.research.advanced_multi_source_aggregator import AdvancedMultiSourceAggregator


async def test_podcast_generation(config_path: str = None, template: str = None, topic: str = None):
    """
    Test podcast generation with a configuration
    
    Args:
        config_path: Path to YAML config file
        template: Built-in template name
        topic: Custom topic for quick test
    """
    
    print("\n" + "="*70)
    print("🧪 PODCAST GENERATION TEST")
    print("="*70 + "\n")
    
    # Load or create config
    if config_path:
        print(f"📁 Loading config from: {config_path}")
        config = ConfigManager.load_config(config_path)
    elif template:
        print(f"📋 Using template: {template}")
        template_map = {
            "tech": ConfigTemplates.tech_startups,
            "gaming": ConfigTemplates.gaming,
            "business": ConfigTemplates.business_finance,
            "sports": ConfigTemplates.sports,
            "science": ConfigTemplates.science
        }
        config = template_map.get(template, ConfigTemplates.tech_startups)()
    elif topic:
        print(f"🎯 Quick test for topic: {topic}")
        config = ConfigTemplates.custom(
            name=f"Test: {topic}",
            description=f"Quick test for {topic}",
            topics=[topic],
            sources={
                "reddit": ["all"],
                "twitter": [],
                "rss": []
            }
        )
    else:
        print("❌ Must provide --profile, --template, or --topic")
        return
    
    print(f"\n✅ Configuration loaded:")
    print(f"   Name: {config.name}")
    print(f"   Type: {config.podcast_type.value}")
    print(f"   Topics: {', '.join(config.topics[:5])}")
    print(f"   Frequency: {config.production.update_frequency}")
    print(f"   Length: {config.production.target_length_minutes} minutes")
    
    # Initialize aggregator
    print(f"\n🔧 Initializing multi-source aggregator...")
    aggregator = AdvancedMultiSourceAggregator()
    
    # Use first topic for test
    test_topic = config.topics[0] if config.topics else "test topic"
    
    print(f"\n🔍 Testing research for: {test_topic}")
    print(f"   This will fetch from configured sources...")
    print(f"   Sources: {len(config.sources.subreddits)} subreddits, {len(config.sources.twitter_accounts)} Twitter accounts\n")
    
    # Run research (limited for test)
    try:
        result = await aggregator.aggregate_all(
            topic=test_topic,
            days_back=3,  # Only last 3 days for test
            max_sources_per_platform=20  # Limit for faster test
        )
        
        print("\n" + "="*70)
        print("📊 TEST RESULTS")
        print("="*70 + "\n")
        
        print(f"✅ Research completed successfully!")
        print(f"\n📈 Statistics:")
        print(f"   Total sources found: {result['total_sources']}")
        
        for platform, data in result['platforms'].items():
            print(f"   - {platform.capitalize()}: {data['count']} items")
        
        if result.get('ai_analysis'):
            analysis = result['ai_analysis']
            print(f"\n🤖 AI Analysis:")
            print(f"   Main narrative: {analysis.get('main_narrative', 'N/A')[:200]}...")
            print(f"   Credibility score: {analysis.get('credibility_score', 0):.0%}")
            
            if analysis.get('key_facts'):
                print(f"\n🎯 Key Facts ({len(analysis['key_facts'])} found):")
                for i, fact in enumerate(analysis['key_facts'][:5], 1):
                    if isinstance(fact, dict):
                        print(f"   {i}. {fact.get('fact', fact)[:100]}...")
                    else:
                        print(f"   {i}. {fact[:100]}...")
        
        # Save test results
        output_dir = Path("output/tests")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"test_{timestamp}.json"
        
        import json
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"\n💾 Test results saved to: {output_file}")
        
        print(f"\n✅ TEST PASSED!")
        print(f"\n🚀 Next steps:")
        print(f"   1. Review results in: {output_file}")
        print(f"   2. If quality is good, proceed to full generation")
        print(f"   3. Configure automation (see MIGRATION_CHECKLIST.md)")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED!")
        print(f"   Error: {str(e)}")
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Check your API keys in .env")
        print(f"   2. Verify internet connection")
        print(f"   3. Review configuration")
        print(f"   4. See MULTI_SOURCE_SETUP_GUIDE.md")
        raise


def main():
    parser = argparse.ArgumentParser(description="Test podcast generation")
    parser.add_argument("--profile", help="Path to configuration YAML file")
    parser.add_argument("--template", choices=["tech", "gaming", "business", "sports", "science"], 
                       help="Use built-in template")
    parser.add_argument("--topic", help="Quick test with custom topic")
    
    args = parser.parse_args()
    
    asyncio.run(test_podcast_generation(
        config_path=args.profile,
        template=args.template,
        topic=args.topic
    ))


if __name__ == "__main__":
    main()
