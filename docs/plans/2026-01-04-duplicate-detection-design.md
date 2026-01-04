# Find Duplicates Feature - Design Document

**Date:** 2026-01-04
**Status:** Approved

## Overview

Add an on-demand "Find Duplicates" button to the refresh page that scans the user's Still Reserve for similar content. Results appear in a new "duplicates" category within "Stills Needing Attention." Users review duplicate pairs side-by-side and choose which to keep - the other is retired.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scan trigger | On-demand only | User control, avoids slow automatic scans |
| Similarity threshold | Configurable (default 90%) | Flexibility via `duplicate_similarity_threshold` setting |
| Merge behavior | User picks winner | Side-by-side comparison gives maximum control |
| Loser handling | Retire (not delete) | Preserves history, non-destructive |

## API Design

### POST /api/refresh/find-duplicates

Scans all active stills for the user, comparing content within each `still_type` group.

**Response:**
```json
{
  "duplicates": [
    {
      "still_a": { "id": "abc", "content": "...", "created_at": "...", "usage_count": 5, ... },
      "still_b": { "id": "def", "content": "...", "created_at": "...", "usage_count": 0, ... },
      "similarity": 0.92
    }
  ],
  "threshold_used": 0.90,
  "stills_scanned": 150
}
```

### POST /api/refresh/merge-duplicates

Retires the loser still, keeping the winner active.

**Request:**
```json
{
  "winner_id": "abc123",
  "loser_id": "def456"
}
```

**Response:**
```json
{
  "success": true,
  "retired_still_id": "def456"
}
```

## Service Layer

### app/services/refresh_tasks.py

```python
async def find_duplicate_stills(user_id: int) -> dict:
    """
    Find duplicate stills in user's library.

    Returns dict with:
    - duplicates: list of {still_a, still_b, similarity} pairs
    - threshold_used: float
    - stills_scanned: int
    """
    threshold = float(await get_global_setting('duplicate_similarity_threshold', '0.90'))

    # Get all active stills for user
    # Group by still_type
    # Compare all pairs within each group using calculate_similarity()
    # Return pairs above threshold, sorted by similarity desc

async def merge_duplicate_stills(winner_id: str, loser_id: str, user_id: int) -> dict:
    """
    Retire the loser still, keeping the winner active.

    Returns dict with:
    - success: bool
    - retired_still_id: str
    """
    # Verify both stills belong to user
    # Update loser: status = 'retired'
    # Return result
```

## UI Design

### Button Placement

Add "Find Duplicates" button next to "Run Maintenance Check" in header:

```html
<div class="flex gap-3">
    <button id="find-duplicates-btn" class="btn btn-secondary">
        Find Duplicates
    </button>
    <button id="run-maintenance-btn" class="btn btn-primary">
        Run Maintenance Check
    </button>
</div>
```

### Duplicates Category

New category in "Stills Needing Attention" after scan:

```
Stills Needing Attention [12]
├── Duplicates Found (3)
│   ├── "Key insight about..." (92%)
│   ├── "Another duplicate..." (91%)
│   └── "Third match..." (90%)
├── Expired (5)
├── Needs Review (2)
└── Never Used (2)
```

### Side-by-Side Comparison Modal

```
┌──────────────────────────────────────────────────────────┐
│  Merge Duplicates                              [X]       │
│  92% similarity                                          │
├────────────────────────┬─────────────────────────────────┤
│  STILL A               │  STILL B                        │
│  Created: Jan 2, 2026  │  Created: Jan 4, 2026           │
│  Used: 5 times         │  Used: 0 times                  │
│  Type: insight         │  Type: insight                  │
│  Source: podcast.mp3   │  Source: transcript.txt         │
│                        │                                 │
│  "Key insight about    │  "A key insight about           │
│   customer behavior    │   customer behavior and         │
│   and engagement..."   │   engagement metrics..."        │
│                        │                                 │
│  [KEEP THIS ONE]       │  [KEEP THIS ONE]                │
├────────────────────────┴─────────────────────────────────┤
│  [Skip - Not Duplicates]                                 │
└──────────────────────────────────────────────────────────┘
```

## Implementation Flow

### Scan Flow

1. User clicks "Find Duplicates"
2. Button shows spinner: "Scanning..."
3. POST /api/refresh/find-duplicates
4. Backend scans and returns duplicate pairs
5. If duplicates found:
   - Add "duplicates" category to dashboard data
   - Re-render stills list
   - Show toast: "Found X duplicate pairs"
6. If none found:
   - Show toast: "No duplicates found above 90% similarity"

### Merge Flow

1. User clicks duplicate pair → opens comparison modal
2. User clicks "Keep This One" on their choice
3. POST /api/refresh/merge-duplicates { winner_id, loser_id }
4. Backend retires loser still
5. Frontend removes pair from list, shows toast

## Files to Modify

| File | Changes |
|------|---------|
| `app/services/refresh_tasks.py` | Add `find_duplicate_stills()`, `merge_duplicate_stills()` |
| `app/api/refresh.py` | Add `/refresh/find-duplicates`, `/refresh/merge-duplicates` endpoints |
| `frontend/refresh.html` | Add button, comparison modal HTML |
| `frontend/static/refresh.js` | Add scan/merge JavaScript functions |

## Error Handling

- **Scan timeout:** Show progress indicator for large libraries
- **Still already retired:** Skip gracefully, remove from results
- **Network error:** Toast with retry option
- **Invalid still ID:** Return 404 with clear message

## Settings

New setting: `duplicate_similarity_threshold`
- Default: `0.90`
- Range: 0.0 to 1.0
- Description: Minimum similarity score to flag as duplicate
