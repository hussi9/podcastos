"""
PodcastOS - Public SaaS Application
Production-Ready v2.0
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Import Routers
from src.app.routers import pages, api, auth, billing

load_dotenv(override=True)

def create_app() -> FastAPI:
    app = FastAPI(title="PodcastOS", version="2.0.0")

    # Static Files
    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        static_dir.mkdir(parents=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Output Files (for downloads)
    output_dir = Path("./output")
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    app.mount("/files", StaticFiles(directory=str(output_dir)), name="files")

    # Include Routers
    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(auth.router, prefix="/api/auth")
    
    # Billing
    app.include_router(billing.router, prefix="/api/billing")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "mode": "production"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app.main:app", host="0.0.0.0", port=8000, reload=True)
