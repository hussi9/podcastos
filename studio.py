#!/usr/bin/env python
"""
PodcastOS Studio - Complete podcast generation and management CLI.

Usage:
    python studio.py generate --profile tech --name "Tech Daily"
    python studio.py play
    python studio.py list
    python studio.py serve
"""

import os
import sys
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))


def print_banner():
    """Print studio banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗  ██████╗ ██████╗  ██████╗ █████╗ ███████╗████████╗  ║
║   ██╔══██╗██╔═══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝  ║
║   ██████╔╝██║   ██║██║  ██║██║     ███████║███████╗   ██║     ║
║   ██╔═══╝ ██║   ██║██║  ██║██║     ██╔══██║╚════██║   ██║     ║
║   ██║     ╚██████╔╝██████╔╝╚██████╗██║  ██║███████║   ██║     ║
║   ╚═╝      ╚═════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝     ║
║                        ██████╗ ███████╗                        ║
║                       ██╔═══██╗██╔════╝                        ║
║                       ██║   ██║███████╗                        ║
║                       ██║   ██║╚════██║                        ║
║                       ╚██████╔╝███████║                        ║
║                        ╚═════╝ ╚══════╝                        ║
║                                                               ║
║              AI-Powered Podcast Studio                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)


async def cmd_generate(args):
    """Generate a new podcast episode."""
    from src.intelligence.pipeline import run_pipeline

    print(f"\n🎙️  Generating {args.profile} podcast: {args.name}")
    print(f"📊 Max topics: {args.topics}")
    print(f"🎵 Audio: {'Yes' if not args.no_audio else 'No'}")
    print(f"⚡ Quick mode: {'Yes' if args.quick else 'No'}")
    print("-" * 50)

    results = await run_pipeline(
        profile_type=args.profile,
        podcast_name=args.name,
        max_topics=args.topics,
        quick_mode=args.quick,
        generate_audio=not args.no_audio,
        output_dir=args.output,
    )

    if results.get("success"):
        print("\n✅ Podcast generated successfully!")
        if results.get("audio_path"):
            print(f"\n🎧 Play with: python studio.py play --file {results['audio_path']}")
        print(f"🌐 Or open player: python studio.py serve")
    else:
        print(f"\n❌ Generation failed: {results.get('errors')}")

    return results


def cmd_list(args):
    """List available episodes."""
    output_dir = Path(args.output)

    print(f"\n📁 Episodes in {output_dir}:\n")

    manifests = list(output_dir.glob("*_manifest.json"))

    if not manifests:
        print("   No episodes found. Generate one with: python studio.py generate")
        return

    for manifest_path in sorted(manifests, reverse=True):
        with open(manifest_path) as f:
            data = json.load(f)

        duration = data.get("total_duration_seconds", 0)
        segments = len(data.get("segments", []))
        generated = data.get("generated_at", "Unknown")[:10]

        print(f"   📻 {data.get('title', 'Untitled')}")
        print(f"      ID: {data.get('episode_id', 'N/A')}")
        print(f"      Duration: {duration // 60:.0f}:{duration % 60:02.0f}")
        print(f"      Segments: {segments}")
        print(f"      Generated: {generated}")
        print()


def cmd_play(args):
    """Play a podcast episode."""
    import subprocess

    if args.file:
        audio_path = args.file
    else:
        # Find most recent episode
        output_dir = Path(args.output)
        audio_files = list(output_dir.glob("*_complete.wav"))

        if not audio_files:
            print("❌ No audio files found. Generate an episode first.")
            return

        audio_path = str(sorted(audio_files, key=lambda x: x.stat().st_mtime, reverse=True)[0])

    print(f"\n🎧 Playing: {audio_path}")
    print("   Press Ctrl+C to stop\n")

    try:
        subprocess.run(["afplay", audio_path])
    except KeyboardInterrupt:
        print("\n⏹️  Playback stopped")
    except FileNotFoundError:
        print("❌ afplay not found. Try: open " + audio_path)


def cmd_serve(args):
    """Start the web player server."""
    import uvicorn

    os.environ["EPISODES_DIR"] = args.output

    print_banner()
    print(f"\n🌐 Starting PodcastOS Player...")
    print(f"📁 Episodes: {args.output}")
    print(f"🔗 Open: http://{args.host}:{args.port}/player")
    print(f"\n   Press Ctrl+C to stop\n")

    uvicorn.run(
        "src.player.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


def cmd_dashboard(args):
    """Start the full studio dashboard."""
    import uvicorn

    os.environ["EPISODES_DIR"] = args.output

    print_banner()
    print(f"\n🎙️  Starting PodcastOS Studio Dashboard...")
    print(f"📁 Episodes: {args.output}")
    print(f"🔗 Dashboard: http://{args.host}:{args.port}/dashboard")
    print(f"🎧 Player: http://{args.host}:{args.port}/player")
    print(f"\n   Press Ctrl+C to stop\n")

    uvicorn.run(
        "src.studio.dashboard_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


def cmd_status(args):
    """Show studio status."""
    print_banner()

    # Check API keys
    print("\n🔑 API Keys:")
    gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    print(f"   Gemini: {'✅ Set' if gemini_key else '❌ Missing'}")

    newsdata_key = os.getenv("NEWSDATA_API_KEY")
    print(f"   NewsData: {'✅ Set' if newsdata_key else '⚠️  Optional'}")

    reddit_id = os.getenv("REDDIT_CLIENT_ID")
    print(f"   Reddit: {'✅ Set' if reddit_id else '⚠️  Optional'}")

    exa_key = os.getenv("EXA_API_KEY")
    print(f"   Exa: {'✅ Set' if exa_key else '⚠️  Optional'}")

    # Check output directory
    output_dir = Path(args.output)
    print(f"\n📁 Output Directory: {output_dir}")

    if output_dir.exists():
        manifests = list(output_dir.glob("*_manifest.json"))
        audio_files = list(output_dir.glob("*_complete.wav"))
        print(f"   Episodes: {len(manifests)}")
        print(f"   Audio files: {len(audio_files)}")

        # Total audio duration
        total_size = sum(f.stat().st_size for f in audio_files)
        print(f"   Total size: {total_size / (1024*1024):.1f} MB")
    else:
        print("   Directory doesn't exist yet")

    print("\n📋 Available Commands:")
    print("   generate  - Create a new podcast episode")
    print("   list      - List available episodes")
    print("   play      - Play an episode locally")
    print("   serve     - Start web player")
    print("   status    - Show this status")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PodcastOS Studio - AI-Powered Podcast Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output", default="./output", help="Output directory")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a new podcast")
    gen_parser.add_argument("--profile", choices=["tech", "finance", "immigration"],
                           default="tech", help="Podcast profile")
    gen_parser.add_argument("--name", default="Tech Daily", help="Podcast name")
    gen_parser.add_argument("--topics", type=int, default=3, help="Max topics")
    gen_parser.add_argument("--quick", action="store_true", help="Quick mode")
    gen_parser.add_argument("--no-audio", action="store_true", help="Skip audio")

    # List command
    list_parser = subparsers.add_parser("list", help="List episodes")

    # Play command
    play_parser = subparsers.add_parser("play", help="Play an episode")
    play_parser.add_argument("--file", help="Specific audio file to play")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start web player")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port")
    serve_parser.add_argument("--reload", action="store_true", help="Auto-reload")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show status")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Start studio dashboard")
    dash_parser.add_argument("--host", default="127.0.0.1", help="Host")
    dash_parser.add_argument("--port", type=int, default=8000, help="Port")
    dash_parser.add_argument("--reload", action="store_true", help="Auto-reload")

    args = parser.parse_args()

    if args.command == "generate":
        asyncio.run(cmd_generate(args))
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "play":
        cmd_play(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    else:
        print_banner()
        parser.print_help()


if __name__ == "__main__":
    main()
