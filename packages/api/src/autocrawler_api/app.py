"""FastAPI app factory."""

from fastapi import FastAPI

from autocrawler_api.routes import health, crawl


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AutoCrawler API",
        description="REST API for the autocrawler web scraping engine",
        version="0.1.0",
    )

    app.include_router(health.router)
    app.include_router(crawl.router)

    return app


app = create_app()
