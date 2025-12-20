#!/usr/bin/env python3
"""
Generate podcast using Google NotebookLM Podcast API.
This uses the standalone Podcast API which doesn't require NotebookLM Enterprise.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import httpx
from dotenv import load_dotenv

load_dotenv()

# Configuration
PROJECT_ID = "desilist-455007"
LOCATION = "global"
API_BASE = f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}"

# Scopes needed for Discovery Engine API
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def get_access_token():
    """Get access token from service account."""
    credentials_path = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        "config/google-service-account.json"
    )

    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES
    )

    credentials.refresh(Request())
    return credentials.token


async def generate_podcast(content: str, title: str, focus: str = None, length: str = "STANDARD"):
    """
    Generate a podcast using the NotebookLM Podcast API.

    Args:
        content: The text content to convert to podcast
        title: Title of the podcast
        focus: Optional focus/direction for the podcast
        length: "SHORT" (4-5 min) or "STANDARD" (~10 min)

    Returns:
        Operation name for polling/downloading
    """
    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Build request body
    body = {
        "podcastConfig": {
            "length": length,
            "languageCode": "en-US",
        },
        "contexts": [
            {"text": content}
        ],
        "title": title,
        "description": f"Desi Daily Podcast - {datetime.now().strftime('%B %d, %Y')}",
    }

    if focus:
        body["podcastConfig"]["focus"] = focus

    url = f"{API_BASE}/podcasts"

    print(f"Calling Podcast API: {url}")
    print(f"Content length: {len(content)} characters")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=body)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

        result = response.json()
        operation_name = result.get("name")
        print(f"Podcast generation started: {operation_name}")
        return operation_name


async def check_operation_status(operation_name: str):
    """Check the status of a long-running operation."""
    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
    }

    url = f"https://discoveryengine.googleapis.com/v1/{operation_name}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Status check error: {response.status_code}")
            print(response.text)
            return None

        return response.json()


async def download_podcast(operation_name: str, output_path: str):
    """Download the generated podcast MP3."""
    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
    }

    url = f"https://discoveryengine.googleapis.com/v1/{operation_name}:download?alt=media"

    print(f"Downloading podcast from: {url}")

    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Download error: {response.status_code}")
            print(response.text)
            return False

        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"Podcast saved to: {output_path}")
        return True


async def wait_for_completion(operation_name: str, max_wait_seconds: int = 600):
    """Wait for podcast generation to complete."""
    print("Waiting for podcast generation...")
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        status = await check_operation_status(operation_name)

        if status is None:
            print("Failed to get status")
            return False

        if status.get("done"):
            if "error" in status:
                print(f"Generation failed: {status['error']}")
                return False
            print("Podcast generation complete!")
            return True

        # Show progress
        metadata = status.get("metadata", {})
        progress = metadata.get("progress", "in progress")
        print(f"  Status: {progress}...")

        await asyncio.sleep(10)  # Poll every 10 seconds

    print("Timeout waiting for podcast generation")
    return False


async def generate_full_podcast():
    """Full workflow: read content, generate podcast, download MP3."""

    # Read the NotebookLM export content
    today = datetime.now().strftime("%Y%m%d")
    content_path = Path(f"output/notebooklm/desi-daily-{today}.txt")

    if not content_path.exists():
        print(f"Content file not found: {content_path}")
        print("Running export script first...")

        # Run the export
        from export_for_notebooklm import export_topics_for_notebooklm
        await export_topics_for_notebooklm()

    # Read the content
    with open(content_path, "r") as f:
        content = f.read()

    print(f"Loaded content: {len(content)} characters")

    # Generate podcast
    title = f"Desi Daily - {datetime.now().strftime('%B %d, %Y')}"
    focus = """Create an engaging podcast discussion between two hosts about news and topics
    affecting South Asian immigrants in the United States. The hosts should sound like
    intelligent friends having a natural conversation. Include specific facts, statistics,
    and expert opinions from the content. Show genuine emotions - frustration about systemic
    issues, hope for positive changes. Do NOT use forced cultural slang like 'yaar' or 'na?'.
    Group related topics together and use clear transitions."""

    operation_name = await generate_podcast(
        content=content,
        title=title,
        focus=focus,
        length="STANDARD"  # ~10 minutes
    )

    if not operation_name:
        print("Failed to start podcast generation")
        return None

    # Wait for completion
    success = await wait_for_completion(operation_name)

    if not success:
        return None

    # Download the podcast
    output_dir = Path("output/notebooklm/audio")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"desi-daily-{today}-notebooklm.mp3"

    downloaded = await download_podcast(operation_name, str(output_path))

    if downloaded:
        print(f"\n{'='*60}")
        print("PODCAST READY!")
        print(f"{'='*60}")
        print(f"File: {output_path}")
        print(f"Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        return str(output_path)

    return None


if __name__ == "__main__":
    asyncio.run(generate_full_podcast())
