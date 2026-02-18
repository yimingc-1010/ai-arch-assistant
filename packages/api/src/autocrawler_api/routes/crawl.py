"""Crawl endpoints.

TODO: Implement:
- POST /crawl - submit a URL to crawl
- GET /crawl/{id} - get crawl result by ID
"""

from fastapi import APIRouter

router = APIRouter(prefix="/crawl", tags=["crawl"])


@router.post("")
async def create_crawl(url: str):
    """Submit a URL to crawl."""
    # TODO: implement
    return {"message": "not implemented", "url": url}


@router.get("/{crawl_id}")
async def get_crawl(crawl_id: int):
    """Get crawl result by ID."""
    # TODO: implement
    return {"message": "not implemented", "id": crawl_id}
