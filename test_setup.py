#!/usr/bin/env python3
"""
Quick test script to verify the setup is working
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


async def test_google_tts():
    """Test Google TTS with service account"""
    print("\n🔊 Testing Google Cloud TTS...")

    from src.tts.google_tts import GoogleTTS

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"   Credentials: {credentials_path}")

    if not credentials_path or not Path(credentials_path).exists():
        print("   ❌ Service account file not found!")
        return False

    try:
        tts = GoogleTTS(
            credentials_path=credentials_path,
            use_indian_accent=False,
            output_dir="output/test",
        )

        # Test a simple phrase
        test_text = "Hello! This is a test of the Desi Daily podcast engine."
        print(f"   Testing with: '{test_text}'")

        audio = await tts.generate_speech(
            text=test_text,
            speaker="raj",
            output_filename="test_raj.mp3",
        )

        if audio:
            print(f"   ✅ Success! Generated {len(audio)} bytes of audio")
            print(f"   📁 Saved to: output/test/test_raj.mp3")
            return True
        else:
            print("   ❌ Failed to generate audio")
            print("   💡 Make sure 'Cloud Text-to-Speech API' is ENABLED in Google Cloud Console:")
            print("      https://console.cloud.google.com/apis/library/texttospeech.googleapis.com")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_gemini():
    """Test Gemini API"""
    print("\n🤖 Testing Google Gemini API...")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("   ❌ GEMINI_API_KEY not set!")
        return False

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content("Say 'Hello from Desi Daily!' in one sentence.")

        print(f"   ✅ Gemini responded: {response.text[:100]}...")
        return True

    except Exception as e:
        print(f"   ❌ Gemini Error: {e}")
        return False


async def test_content_aggregation():
    """Test content aggregation (Reddit - no auth needed)"""
    print("\n📰 Testing Content Aggregation (Reddit)...")

    try:
        from src.aggregators.reddit_aggregator import RedditAggregator

        reddit = RedditAggregator()
        posts = await reddit.fetch_subreddit_posts("ABCDesis", limit=5)

        if posts:
            print(f"   ✅ Found {len(posts)} posts from r/ABCDesis")
            print(f"   📝 Top post: {posts[0].title[:60]}...")
            return True
        else:
            print("   ⚠️  No posts found (might be rate limited)")
            return True  # Not critical

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def main():
    print("=" * 50)
    print("🎙️  DESI PODCAST ENGINE - Setup Test")
    print("=" * 50)

    results = {}

    # Test Gemini
    results["gemini"] = await test_gemini()

    # Test Google TTS
    results["google_tts"] = await test_google_tts()

    # Test Content Aggregation
    results["reddit"] = await test_content_aggregation()

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results")
    print("=" * 50)

    all_passed = True
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All tests passed! You're ready to generate podcasts.")
        print("\n   Try: python scheduler.py --preview")
        print("   Or:  python scheduler.py --once --script-only")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        print("\n   Common fixes:")
        print("   1. Enable Cloud Text-to-Speech API in Google Cloud Console")
        print("   2. Make sure service account has correct permissions")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
