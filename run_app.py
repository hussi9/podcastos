#!/usr/bin/env python
"""Run the PodcastOS web application."""

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main():
    import argparse

    # Railway provides PORT env var
    default_port = int(os.getenv("PORT", 8000))
    # In production (Railway), bind to 0.0.0.0
    is_production = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT")
    default_host = "0.0.0.0" if is_production else "127.0.0.1"

    parser = argparse.ArgumentParser(description="PodcastOS Web App")
    parser.add_argument("--host", default=default_host, help="Host")
    parser.add_argument("--port", type=int, default=default_port, help="Port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload")

    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   🎙️  PodcastOS - AI Content Studio                          ║
║                                                               ║
║   Landing:  http://{args.host}:{args.port}/                           ║
║   App:      http://{args.host}:{args.port}/app                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "src.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload if not is_production else False,
    )


if __name__ == "__main__":
    main()
