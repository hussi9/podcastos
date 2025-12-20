"""Run the interactive podcast player."""

import os
import sys
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))


def main():
    """Run the player server."""
    import argparse

    parser = argparse.ArgumentParser(description="PodcastOS Interactive Player")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--episodes-dir", default="./output", help="Episodes directory")

    args = parser.parse_args()

    # Set episodes directory
    os.environ["EPISODES_DIR"] = args.episodes_dir

    print(f"\n🎙️  PodcastOS Player starting...")
    print(f"📁 Episodes directory: {args.episodes_dir}")
    print(f"🌐 Open http://{args.host}:{args.port}/player in your browser\n")

    uvicorn.run(
        "src.player.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
