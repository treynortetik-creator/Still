# Still Type Expansion & Lifecycle Management Design

**Date:** 2026-01-03
**Status:** Approved

## Overview

Expand the still type system from 6 to 10 types and add lifecycle management fields to enable the "Refresh" phase of the PADR content repurposing framework.

## Success Criteria

- All 10 still types work end-to-end
- Lifecycle fields are captured during distillation
- Reserve shows new filters and usage data
- Still usage is tracked when content is generated

---

## 1. Database Schema Changes

### New Still Types

| Type | Description | Example |
|------|-------------|---------|
| `framework` | Methodologies, step-by-step processes | "3-step approach to facility optimization" |
| `definition` | Concept explanations, glossary-style | "Ambient monitoring is..." |
| `question` | FAQs, objections, challenges | "What about compliance concerns?" |
| `proof_point` | Third-party validation, citations | "As featured in Healthcare Weekly..." |

### Migration SQL

```sql
-- Rename existing fields for consistency
ALTER TABLE stills RENAME COLUMN times_used TO usage_count;
ALTER TABLE stills RENAME COLUMN last_used TO last_used_at;

-- Add new lifecycle fields
ALTER TABLE stills ADD COLUMN status TEXT DEFAULT 'active'
  CHECK (status IN ('active', 'evergreen', 'needs_review', 'retired'));

ALTER TABLE stills ADD COLUMN best_formats TEXT[];

ALTER TABLE stills ADD COLUMN funnel_stage TEXT
  CHECK (funnel_stage IN ('awareness', 'consideration', 'decision'));

ALTER TABLE stills ADD COLUMN expiration_type TEXT
  CHECK (expiration_type IN ('date_bound', 'event_bound', 'evergreen'));

ALTER TABLE stills ADD COLUMN expiration_date DATE;

ALTER TABLE stills ADD COLUMN performance TEXT DEFAULT 'untested'
  CHECK (performance IN ('high', 'medium', 'low', 'untested'));

-- Indexes for lifecycle queries
CREATE INDEX idx_stills_status ON stills(status);
CREATE INDEX idx_stills_expiration ON stills(expiration_date) WHERE expiration_date IS NOT NULL;
```

### Files to Update

- `app/models/stills.py` - Add new enum values, update Pydantic models
- `app/database.py` - Update schema references
- `app/services/library_manager.py` - Update validation

---

## 2. Distillation Prompt Updates

### Changes

1. Add 4 new still type sections (framework, definition, question, proof_point)
2. Include Source of Truth context at top to guide extraction
3. Add new fields per still: `best_formats`, `funnel_stage`, `expiration_date`
4. Dynamic extraction targets based on content length

### New Prompt Structure

```
## SOURCE OF TRUTH CONTEXT:
Core Narratives: {core_narratives}
Primary Pain Point: {primary_pain_point}
The Promise: {the_promise}

## STILL TYPES TO EXTRACT:

1. DATA - statistics, metrics, ROI figures
2. INSIGHT - frameworks, methods, actionable tips
3. STORY - customer examples, anecdotes, case studies
4. PROBLEM - challenges, pain points, obstacles
5. SOLUTION - recommendations, strategies, tools
6. QUOTE - memorable statements with attribution
7. FRAMEWORK - methodologies, step-by-step processes
8. DEFINITION - concept explanations, glossary-style
9. QUESTION - FAQs, objections, common challenges
10. PROOF_POINT - third-party validation, citations

## ENHANCED OUTPUT FORMAT:
{
  "type": "data",
  "content": "40% reduction in manual charting",
  "source_location": "14:32",
  "best_formats": ["linkedin", "email", "sales"],
  "funnel_stage": "consideration",
  "expiration_date": "2025-12-01",
  "relevance_to_persona": 5
}

## EXTRACTION SCALE:
- Short content (<2000 words): 8-15 stills
- Medium content (2000-5000 words): 15-30 stills
- Long content (>5000 words): 30-50 stills
```

### Files to Update

- `data/prompts/distillation.txt`
- `data/prompts/distillation_pass2.txt`
- `app/services/distillation.py` - Parse new fields, pass Source of Truth context

---

## 3. Reserve UI Changes

### New Filter Controls

```
[Type v] [Status v] [Funnel Stage v] [Sort By v]
```

| Filter | Options |
|--------|---------|
| Type | All 10 types |
| Status | active, evergreen, needs_review, retired |
| Funnel Stage | awareness, consideration, decision |
| Sort By | newest, oldest, most used, never used, expiring soon |

### New Type Colors

```javascript
const typeColors = {
  // existing 6...
  'framework':   { bg: 'rgba(45, 212, 191, 0.15)',  text: '#2DD4BF' },  // Teal
  'definition':  { bg: 'rgba(148, 163, 184, 0.15)', text: '#94A3B8' },  // Slate
  'question':    { bg: 'rgba(244, 114, 182, 0.15)', text: '#F472B6' },  // Pink
  'proof_point': { bg: 'rgba(34, 197, 94, 0.15)',   text: '#22C55E' }   // Emerald
};
```

### Card Enhancements

```
+---------------------------------------------+
| [DATA]  [awareness]  [! Expires: 14d]       |  <- status badges
|                                             |
| "40% reduction in manual charting..."       |
|                                             |
| Used 12 times  |  Last: Jan 2               |  <- usage stats
| Best for: linkedin, email                   |  <- format hints
+---------------------------------------------+
```

### Visual Warnings

- Expiration within 30 days: amber warning badge
- Expiration within 7 days: red warning badge
- `needs_review` status: yellow border highlight
- `retired` status: grayed out / strikethrough

### Files to Update

- `frontend/reserve.html` - Filters, colors, card template, sort options

---

## 4. Usage Tracking

### Implementation

In `app/services/drafting.py`:

```python
async def record_still_usage(db, still_ids: list[str], output_id: int):
    """Increment usage counts and update timestamps for stills used in output."""
    now = datetime.utcnow()

    await db.execute("""
        UPDATE stills
        SET usage_count = usage_count + 1,
            last_used_at = $1
        WHERE id = ANY($2)
    """, now, still_ids)

    await db.execute("""
        UPDATE outputs
        SET atoms_used = $1
        WHERE id = $2
    """, json.dumps(still_ids), output_id)
```

### Call Site

After output is saved in `create_draft()`:

```python
if stills_used:
    still_ids = [s['id'] for s in stills_used]
    await record_still_usage(db, still_ids, output_id)
```

### Files to Update

- `app/services/drafting.py` - Add tracking function, wire up call sites

---

## 5. Auto-Status Utility

### New File: `app/services/lifecycle.py`

```python
async def check_expiring_stills(db, days_threshold: int = 30) -> int:
    """Mark stills as needs_review when expiration is approaching."""

    result = await db.execute("""
        UPDATE stills
        SET status = 'needs_review'
        WHERE status = 'active'
          AND expiration_date IS NOT NULL
          AND expiration_date <= CURRENT_DATE + INTERVAL '$1 days'
        RETURNING id
    """, days_threshold)

    return len(result)

async def get_lifecycle_summary(db, user_id: int) -> dict:
    """Get counts by status for dashboard/UI."""

    return await db.fetch_one("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'active') as active,
            COUNT(*) FILTER (WHERE status = 'evergreen') as evergreen,
            COUNT(*) FILTER (WHERE status = 'needs_review') as needs_review,
            COUNT(*) FILTER (WHERE status = 'retired') as retired,
            COUNT(*) FILTER (WHERE expiration_date <= CURRENT_DATE + 7) as expiring_soon
        FROM stills WHERE user_id = $1
    """, user_id)
```

### Admin Endpoint

```python
@router.post("/admin/lifecycle/check-expirations")
async def trigger_expiration_check(days: int = 30):
    count = await check_expiring_stills(db, days)
    return {"stills_flagged": count}
```

### Files to Update

- `app/services/lifecycle.py` - New file
- `app/api/admin.py` - Add endpoint
- `frontend/reserve.html` - Show needs_review badge count

---

## Implementation Order

1. **Database migration** - Schema changes first
2. **Backend models** - Update StillType enum, Pydantic models
3. **Distillation prompts** - Update extraction prompts
4. **Distillation service** - Parse new fields, pass Source of Truth
5. **Usage tracking** - Wire up in drafting service
6. **Lifecycle service** - New utility + admin endpoint
7. **Reserve UI** - Filters, colors, cards, warnings
8. **Testing** - End-to-end verification

---

## Notes

- Existing stills will have `status=NULL` initially; migration should set default to 'active'
- `best_formats` uses PostgreSQL TEXT[] array type
- Consider backfilling `funnel_stage` for existing stills based on still_type heuristics
