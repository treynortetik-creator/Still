# Error Logging System - Design Document

**Date:** 2026-01-04
**Status:** Approved

## Overview

Add production error logging to capture errors from beta users, stored in database with admin view for debugging.

**Scope:**
1. **Immediate fix** - Fix duplicate merge UX issue (disable buttons, friendly messages)
2. **Error logging system** - Capture frontend/backend errors to `error_logs` table
3. **Admin page** - Simple view at `/admin/errors` to browse and filter errors

## Database Schema

```sql
CREATE TABLE error_logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    error_type TEXT NOT NULL,           -- 'api_error', 'frontend_error', 'validation_error', 'database_error', 'uncaught_error'
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    source TEXT NOT NULL,               -- 'frontend' or 'backend'
    user_id INTEGER REFERENCES users(id),
    endpoint TEXT,                      -- API endpoint or page URL
    additional_context JSONB            -- browser info, request method, etc.
);

CREATE INDEX idx_error_logs_created_at ON error_logs(created_at DESC);
CREATE INDEX idx_error_logs_user_id ON error_logs(user_id);
CREATE INDEX idx_error_logs_error_type ON error_logs(error_type);
```

## Backend Service

### New File: `app/services/error_logger.py`

```python
import logging
import traceback
from typing import Optional
from app.database import get_db
from app.db_utils import execute

logger = logging.getLogger(__name__)

async def log_error(
    error_type: str,
    error_message: str,
    source: str = "backend",
    user_id: Optional[int] = None,
    endpoint: Optional[str] = None,
    stack_trace: Optional[str] = None,
    additional_context: Optional[dict] = None
) -> None:
    """
    Log an error to the database. Fire-and-forget, never raises.

    Args:
        error_type: Category (api_error, frontend_error, validation_error, database_error, uncaught_error)
        error_message: The error message
        source: 'frontend' or 'backend'
        user_id: User who encountered error (optional)
        endpoint: API endpoint or page URL
        stack_trace: Stack trace if available
        additional_context: Any extra info as dict (stored as JSONB)
    """
    try:
        import json
        from app.config import get_settings
        settings = get_settings()

        async with get_db() as db:
            if settings.use_postgres:
                await db.execute("""
                    INSERT INTO error_logs (error_type, error_message, source, user_id, endpoint, stack_trace, additional_context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, error_type, error_message, source, user_id, endpoint, stack_trace,
                    json.dumps(additional_context) if additional_context else None)
            else:
                await execute(db, """
                    INSERT INTO error_logs (error_type, error_message, source, user_id, endpoint, stack_trace, additional_context)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (error_type, error_message, source, user_id, endpoint, stack_trace,
                      json.dumps(additional_context) if additional_context else None))
                await db.commit()
    except Exception as e:
        # Never raise - just log to console as fallback
        logger.error(f"Failed to log error to database: {e}")


def log_exception(
    error_type: str,
    exception: Exception,
    source: str = "backend",
    user_id: Optional[int] = None,
    endpoint: Optional[str] = None,
    additional_context: Optional[dict] = None
) -> None:
    """Convenience wrapper to log an exception with its stack trace."""
    import asyncio
    asyncio.create_task(log_error(
        error_type=error_type,
        error_message=str(exception),
        source=source,
        user_id=user_id,
        endpoint=endpoint,
        stack_trace=traceback.format_exc(),
        additional_context=additional_context
    ))
```

### API Endpoint for Frontend Errors

Add to `app/api/errors.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.api.auth import get_current_user_id_optional
from app.services.error_logger import log_error

router = APIRouter()

class ErrorLogRequest(BaseModel):
    error_type: str
    error_message: str
    endpoint: Optional[str] = None
    stack_trace: Optional[str] = None
    additional_context: Optional[dict] = None

@router.post("/errors/log")
async def log_frontend_error(
    request: ErrorLogRequest,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Log a frontend error to the database."""
    await log_error(
        error_type=request.error_type,
        error_message=request.error_message,
        source="frontend",
        user_id=user_id,
        endpoint=request.endpoint,
        stack_trace=request.stack_trace,
        additional_context=request.additional_context
    )
    return {"success": True}
```

## Frontend Error Capture

### New File: `frontend/static/error-logger.js`

```javascript
/**
 * Error Logger - Sends errors to backend for tracking
 */
const ErrorLogger = {
    async log(errorType, errorMessage, endpoint = null, stackTrace = null, context = {}) {
        try {
            const token = typeof getToken === 'function' ? getToken() : null;
            await fetch('/api/errors/log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token && { 'Authorization': `Bearer ${token}` })
                },
                body: JSON.stringify({
                    error_type: errorType,
                    error_message: errorMessage,
                    endpoint: endpoint || window.location.pathname,
                    stack_trace: stackTrace,
                    additional_context: {
                        ...context,
                        browser: navigator.userAgent,
                        url: window.location.href,
                        timestamp: new Date().toISOString()
                    }
                })
            });
        } catch (e) {
            // Silently fail - don't create error loops
            console.error('Failed to log error:', e);
        }
    },

    // Map backend errors to user-friendly messages
    friendlyMessage(errorMessage) {
        const friendlyErrors = {
            'Still already retired': 'This pair was already merged.',
            'Winner still not found': 'One of these stills no longer exists.',
            'Loser still not found': 'One of these stills no longer exists.',
            'Still not found': 'This still no longer exists.',
            'Unauthorized': 'Please log in again.',
            'Network Error': 'Connection issue. Please check your internet.',
        };
        return friendlyErrors[errorMessage] || errorMessage;
    }
};

// Global uncaught error handler
window.onerror = function(msg, url, line, col, error) {
    ErrorLogger.log('uncaught_error', msg, url, error?.stack, { line, col });
    return false; // Let default handler run too
};

// Unhandled promise rejection handler
window.onunhandledrejection = function(event) {
    const message = event.reason?.message || String(event.reason);
    ErrorLogger.log('unhandled_rejection', message, window.location.pathname, event.reason?.stack);
};
```

## Admin Page

### New File: `frontend/admin-errors.html`

Simple table view with:
- Filter by error_type, source, time range
- Search error messages
- Click row to expand full details (stack trace, context)
- Pagination
- Count badge showing errors in last 24h

### API Endpoint: `GET /api/admin/errors`

```python
@router.get("/admin/errors")
async def get_error_logs(
    error_type: Optional[str] = None,
    source: Optional[str] = None,
    since: Optional[str] = None,  # ISO date string
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id)
):
    """Get error logs with filters. Admin only."""
    # Verify admin access
    # Query error_logs with filters
    # Return paginated results
```

## Immediate UX Fix

### Changes to `frontend/static/refresh.js`

**1. Disable buttons during merge:**

```javascript
async function mergeDuplicates(winnerId, loserId, pairIndex) {
    // Disable all buttons in modal immediately
    const buttons = document.querySelectorAll('#duplicate-modal button');
    buttons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch('/api/refresh/merge-duplicates', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ winner_id: winnerId, loser_id: loserId })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Merge failed');
        }

        // ... rest of success handling
    } catch (error) {
        console.error('Merge error:', error);

        // Log to database
        ErrorLogger.log('api_error', error.message, '/api/refresh/merge-duplicates', error.stack, {
            winner_id: winnerId,
            loser_id: loserId
        });

        // Show friendly message
        Utils.showToast(ErrorLogger.friendlyMessage(error.message), 'error');
    } finally {
        buttons.forEach(btn => btn.disabled = false);
    }
}
```

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `migrations/XXXX_create_error_logs.sql` | Create | Database migration |
| `app/services/error_logger.py` | Create | Backend logging service |
| `app/api/errors.py` | Create | Frontend error endpoint |
| `app/api/admin.py` | Modify | Add error logs endpoint |
| `app/main.py` | Modify | Register errors router |
| `frontend/static/error-logger.js` | Create | Frontend error capture |
| `frontend/admin-errors.html` | Create | Admin error view page |
| `frontend/static/refresh.js` | Modify | Fix merge UX, add logging |
| All HTML files | Modify | Include error-logger.js |

## Implementation Order

1. **Database migration** - Create error_logs table
2. **Backend service** - error_logger.py
3. **Frontend API endpoint** - POST /api/errors/log
4. **Frontend error logger** - error-logger.js + include in pages
5. **Fix merge UX** - Button disabling + friendly messages + logging
6. **Admin API** - GET /api/admin/errors
7. **Admin page** - admin-errors.html
