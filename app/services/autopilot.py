"""Autopilot service for monitoring RSS/YouTube/podcast feeds."""
import asyncio
import json
import logging
import uuid
import httpx
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.db_utils import execute, fetchone, fetchall, safe_json
from app.utils.background_tasks import create_background_task

logger = logging.getLogger(__name__)
from app.models.job import JobStatus

# Frequency mappings in minutes
FREQUENCY_MINUTES = {
    "hourly": 60,
    "daily": 1440,
    "weekly": 10080
}


async def fetch_rss_feed(url: str) -> dict:
    """
    Fetch and parse an RSS feed.

    Returns:
    {
        'status': 'success' | 'error',
        'items': [...],
        'error': Optional error message
    }
    """
    try:
        # Import feedparser here to make it optional
        import feedparser

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code != 200:
                return {'status': 'error', 'error': f'HTTP {response.status_code}', 'items': []}

            feed = feedparser.parse(response.text)

            items = []
            for entry in feed.entries[:20]:  # Limit to 20 most recent
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except (ValueError, TypeError, IndexError):
                        # Invalid date format in feed entry - skip it
                        pass

                items.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'guid': entry.get('id', entry.get('link', '')),
                    'published': published,
                    'summary': (entry.get('summary', entry.get('description', '')))[:500]
                })

            return {'status': 'success', 'items': items}

    except ImportError:
        return {'status': 'error', 'error': 'feedparser not installed', 'items': []}
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'items': []}


async def fetch_youtube_channel(url: str) -> dict:
    """
    Fetch YouTube channel RSS feed.

    YouTube provides RSS feeds at:
    https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
    """
    # Try to extract channel ID from various URL formats
    channel_id = None

    if 'channel_id=' in url:
        channel_id = url.split('channel_id=')[1].split('&')[0]
    elif '/channel/' in url:
        channel_id = url.split('/channel/')[1].split('/')[0].split('?')[0]
    elif '/c/' in url or '/@' in url:
        # Handle custom URLs - would need to resolve these
        return {'status': 'error', 'error': 'Please use channel ID URL format', 'items': []}

    if channel_id:
        rss_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
        return await fetch_rss_feed(rss_url)

    # If URL is already an RSS feed URL, just fetch it
    if 'feeds/videos.xml' in url:
        return await fetch_rss_feed(url)

    return {'status': 'error', 'error': 'Could not extract channel ID', 'items': []}


async def check_source(source_id: int) -> dict:
    """
    Check a single source for new items.

    Returns:
    {
        'source_id': int,
        'new_items': int,
        'error': Optional[str]
    }
    """
    async with get_db() as db:
        # Get source config
        source = await fetchone(
            db,
            "SELECT * FROM autopilot_sources WHERE id = ? AND is_active = ?",
            (source_id, True)
        )

        if not source:
            return {'source_id': source_id, 'new_items': 0, 'error': 'Source not found or inactive'}

        # Fetch feed based on type
        source_type = source['source_type']
        url = source['source_url']

        if source_type == 'youtube':
            result = await fetch_youtube_channel(url)
        else:  # rss or podcast
            result = await fetch_rss_feed(url)

        if result['status'] == 'error':
            # Update error tracking
            await execute(
                db,
                """
                UPDATE autopilot_sources
                SET last_error = ?, error_count = error_count + 1, last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (result['error'], source_id)
            )
            return {'source_id': source_id, 'new_items': 0, 'error': result['error']}

        # Process new items
        new_items = 0
        for item in result['items']:
            # Check if we've already seen this item
            existing = await fetchone(
                db,
                "SELECT id FROM autopilot_items WHERE source_id = ? AND item_guid = ?",
                (source_id, item['guid'])
            )
            if existing:
                continue  # Already have this item

            # Store the feed item
            await execute(
                db,
                """
                INSERT INTO autopilot_items
                (source_id, user_id, item_guid, item_title, item_url, item_published)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source['user_id'],
                    item['guid'],
                    item['title'],
                    item['link'],
                    item['published']
                )
            )
            new_items += 1

        # Update source metadata
        frequency_minutes = FREQUENCY_MINUTES.get(source['check_frequency'], 1440)
        next_check = datetime.utcnow() + timedelta(minutes=frequency_minutes)

        await execute(
            db,
            """
            UPDATE autopilot_sources
            SET last_checked = CURRENT_TIMESTAMP,
                next_check = ?,
                items_processed = items_processed + ?,
                error_count = 0,
                last_error = NULL
            WHERE id = ?
            """,
            (next_check, new_items, source_id)
        )

        return {'source_id': source_id, 'new_items': new_items}


async def fetch_article_content(url: str) -> tuple[str, bool]:
    """
    Fetch article text content from a URL.
    Returns (content, success) tuple.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed, falling back to raw HTML extraction")
        trafilatura = None

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return f"Failed to fetch URL: HTTP {response.status_code}", False

            if trafilatura:
                text = trafilatura.extract(response.text)
                if text and len(text.strip()) > 100:
                    return text, True

            # Fallback: basic text extraction
            from html.parser import HTMLParser
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self._skip = False
                def handle_starttag(self, tag, attrs):
                    if tag in ('script', 'style', 'nav', 'header', 'footer'):
                        self._skip = True
                def handle_endtag(self, tag):
                    if tag in ('script', 'style', 'nav', 'header', 'footer'):
                        self._skip = False
                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self.text_parts.append(data.strip())

            extractor = TextExtractor()
            extractor.feed(response.text)
            text = ' '.join(extractor.text_parts)
            if len(text) > 200:
                return text[:15000], True

            return "Could not extract meaningful content from URL", False
    except Exception as e:
        return f"Content fetch error: {str(e)}", False


async def create_job_from_feed_item(item_id: int) -> Optional[str]:
    """
    Create a job from a feed item for automatic processing.

    Returns the job_id if created, None if failed.
    """
    async with get_db() as db:
        # Get feed item with source config
        item = await fetchone(
            db,
            """
            SELECT ai.*, s.user_id, s.target_persona, s.asset_types, s.source_name
            FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE ai.id = ? AND ai.processing_status = 'pending'
            """,
            (item_id,)
        )

        if not item:
            return None

        job_id = str(uuid.uuid4())
        asset_types = safe_json(item['asset_types'], ['linkedin'])

        # Default quantities
        asset_quantities = {}
        for asset_type in asset_types:
            asset_quantities[asset_type] = 1

        campaign_name = f"Auto: {item['source_name']} - {(item['item_title'] or 'Untitled')[:30]}"

        # Fetch actual article content instead of storing metadata
        article_content, fetch_success = await fetch_article_content(item['item_url'])

        if not fetch_success:
            await execute(
                db,
                "UPDATE autopilot_items SET processing_status = 'failed' WHERE id = ?",
                (item_id,)
            )
            logger.warning(f"Autopilot: Failed to fetch content for item {item_id} ({item['item_url']}): {article_content}")
            return None

        # Create job record with fetched article content
        await execute(
            db,
            """
            INSERT INTO jobs (
                id, user_id, status, original_filename, file_type,
                target_persona, asset_types, asset_quantities, processing_mode,
                campaign_name, current_step, progress, transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                item['user_id'],
                JobStatus.UPLOADING.value,
                f"autopilot_{item_id}",
                'url',
                item['target_persona'],
                json.dumps(asset_types),
                json.dumps(asset_quantities),
                'autopilot',
                campaign_name,
                'Queued for autopilot processing',
                5,
                article_content
            )
        )

        # Update feed item status
        await execute(
            db,
            "UPDATE autopilot_items SET job_id = ?, processing_status = 'processing' WHERE id = ?",
            (job_id, item_id)
        )


    return job_id


async def process_pending_items(limit: int = 5) -> int:
    """
    Process pending feed items by creating jobs.

    Returns the number of jobs created.
    """
    async with get_db() as db:
        # Get pending items from active sources
        items = await fetchall(
            db,
            """
            SELECT ai.id
            FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE ai.processing_status = 'pending'
            AND s.is_active = ?
            ORDER BY ai.created_at ASC
            LIMIT ?
            """,
            (True, limit)
        )

    jobs_created = 0
    for item in items:
        try:
            job_id = await create_job_from_feed_item(item['id'])
            if job_id:
                jobs_created += 1
                # Trigger job processing
                from app.services.pipeline import process_job
                create_background_task(
                    process_job(job_id),
                    name=f"autopilot_job_{job_id}"
                )
        except Exception as e:
            logger.error(f"Failed to create job for item {item['id']}: {e}")
            # Mark as failed
            async with get_db() as db:
                await execute(
                    db,
                    "UPDATE autopilot_items SET processing_status = 'failed' WHERE id = ?",
                    (item['id'],)
                )

    return jobs_created


async def check_due_sources() -> int:
    """
    Check all sources that are due for an update.

    Returns the number of sources checked.
    """
    async with get_db() as db:
        # Find sources due for checking
        sources = await fetchall(
            db,
            """
            SELECT id, source_name FROM autopilot_sources
            WHERE is_active = ?
            AND (next_check IS NULL OR next_check <= CURRENT_TIMESTAMP)
            LIMIT 5
            """,
            (True,)
        )

    checked = 0
    for source in sources:
        try:
            result = await check_source(source['id'])
            if result.get('new_items', 0) > 0:
                logger.info(f"Source '{source['source_name']}': {result['new_items']} new items")
            checked += 1
        except Exception as e:
            logger.error(f"Error checking source {source['id']}: {e}")

    return checked
