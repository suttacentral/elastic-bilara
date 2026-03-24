"""
Dictionary proxy endpoint for fetching external dictionary data.
This proxies requests to DPDict to avoid CORS issues.
Includes local database caching to reduce external API calls.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import httpx
import logging
from typing import Optional

from app.db.database import get_db
from app.db.models.dictionary_cache import DictionaryCache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dictionary/list")
async def list_dictionary_entries(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Fetch a list of dictionary entries from the local cache.
    """
    normalized_skip = max(skip, 0)
    normalized_limit = min(max(limit, 1), 100)
    normalized_search = (search or "").strip()

    query = (
        db.query(DictionaryCache.word)
        .filter(DictionaryCache.word.isnot(None))
    )

    if normalized_search:
        query = query.filter(
            DictionaryCache.word.ilike(f"%{normalized_search}%")
        )

    rows = (
        query
        .order_by(DictionaryCache.word)
        .offset(normalized_skip)
        .limit(normalized_limit + 1)
        .all()
    )

    has_more = len(rows) > normalized_limit
    rows = rows[:normalized_limit]

    return {
        "skip": normalized_skip,
        "limit": normalized_limit,
        "has_more": has_more,
        "items": [
            {
                "word": row.word,
            }
            for row in rows
        ]
    }


@router.get("/dictionary/{word}")
async def lookup_dictionary(word: str, db: Session = Depends(get_db)):
    """
    Proxy endpoint to fetch Pali dictionary definitions from DPDict.
    Uses local database cache to avoid repeated external API calls.

    Args:
        word: The Pali word to look up
        db: Database session

    Returns:
        JSON response containing summary_html and dpd_html
    """
    # 1. First check the local cache
    cached = db.query(DictionaryCache).filter(DictionaryCache.word == word).first()
    if cached:
        logger.info(f"Cache hit for word: {word}")
        return {
            "summary_html": cached.summary_html,
            "dpd_html": cached.dpd_html
        }

    # 2. No cache, fetch from external API
    url = f"https://www.dpdict.net/search_json?q={word}"
    logger.info(f"Cache miss for word: {word}, fetching from API: {url}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json,text/html,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                follow_redirects=True
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched dictionary for: {word}")

            # 3. Store in local database
            cache_entry = DictionaryCache(
                word=word,
                summary_html=data.get("summary_html"),
                dpd_html=data.get("dpd_html")
            )
            db.add(cache_entry)
            db.commit()
            logger.info(f"Cached dictionary entry for: {word}")

            return data
    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching dictionary for {word}: {e}")
        raise HTTPException(status_code=504, detail=f"Dictionary service timeout: {str(e)}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for {word}: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Dictionary service error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch dictionary for {word}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dictionary: {str(e)}")
