"""FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autocrawler_api.routes import health

# Load .env early so VOYAGE_API_KEY / ANTHROPIC_API_KEY etc. are available
try:
    from lawrag import config as _lawrag_config
    _lawrag_config.load_dotenv()
except ImportError:
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AutoCrawler API",
        description="REST API for the autocrawler web scraping engine",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite admin app (local dev)
            "http://localhost:3000",  # Next.js lawchat app (local dev)
            "http://localhost",       # nginx (Docker, port 80)
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    # lawrag RAG routes (optional — only registered when lawrag is installed)
    try:
        from autocrawler_api.routes import rag
        app.include_router(rag.router)
    except ImportError:
        pass

    # Admin routes
    try:
        from autocrawler_api.routes import admin
        app.include_router(admin.router)
    except ImportError:
        pass

    return app


app = create_app()
