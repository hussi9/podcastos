
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.intelligence.synthesis.content_engine import ContentEngine, ContentInput

router = APIRouter()

class GenerateRequest(BaseModel):
    plan: str = "bundle"
    brand_name: str = "Tech Daily"
    topic: Optional[str] = None
    user_content: Optional[str] = None

@router.post("/generate")
async def generate_content(request: GenerateRequest):
    """
    Generate content (Podcast/Newsletter).
    This handles the core logic that was previously in main.py
    """
    try:
        engine = ContentEngine(output_dir="./output")

        generate_newsletter = request.plan in ["newsletter", "bundle"]
        generate_podcast = request.plan in ["podcast", "bundle"]

        input_data = ContentInput(
            topic=request.topic or "Today's Tech News",
            user_content=request.user_content,
            brand_name=request.brand_name,
            generate_newsletter=generate_newsletter,
            generate_podcast=generate_podcast,
        )

        # In a real async worker queue (Celery/RQ) this would be offloaded
        # For now we await it as per original design
        result = await engine.generate(input_data)

        return {
            "success": result.success,
            "id": result.id,
            "topic": result.topic,
            "word_count": result.word_count,
            "audio_duration_seconds": result.audio_duration_seconds,
            "newsletter_html_path": result.newsletter_html_path,
            "newsletter_markdown_path": result.newsletter_markdown_path,
            "podcast_audio_path": result.podcast_audio_path,
            "errors": result.errors,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

@router.get("/health")
async def api_health():
    return {"status": "online"}
