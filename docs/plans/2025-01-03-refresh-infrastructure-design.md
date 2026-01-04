# Refresh Phase Infrastructure Design

**Date:** 2025-01-03
**Status:** Approved

## Overview

PADR's key innovation is the explicit Refresh step - treating content maintenance as a first-class feature. This design covers infrastructure to surface stale content, track performance, and enable efficient refresh workflows.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dashboard location | Dedicated `/refresh.html` page | Refresh is a first-class PADR phase, deserves its own nav item |
| Source refresh approach | Smart merge with diff view | Shows matched/new/orphaned stills, user reviews and confirms |
| Still matching algorithm | Hybrid: fuzzy first, LLM for uncertain | Fast for obvious matches, accurate for semantic similarity |
| Performance bubble-up | Manual review prompt | User selects which stills contributed when marking output as high performer |

---

## 1. Page Structure & Navigation

### New Files
- `/frontend/refresh.html` - Main refresh dashboard page
- `/frontend/static/refresh.js` - Page-specific JavaScript
- `/app/api/refresh.py` - API endpoints for refresh features
- `/app/services/still_matcher.py` - Hybrid matching logic
- `/app/services/refresh_tasks.py` - Background maintenance tasks
- `/data/prompts/still_matching.txt` - LLM prompt for uncertain matches

### Navigation Update
In `components.js`, add "Refresh" nav item between Reserve and Workshop:
```
Distill → Reserve → Refresh → Workshop → Calendar → Settings
```

### Notification Badge
The nav item shows a badge with count of items needing attention:
```html
<a href="/refresh.html">
  Refresh
  <span class="nav-badge">15</span>
</a>
```

Badge count = sources past review_date + stills with status="needs_review" + stills with expiration_date < today

### Page Layout (Three Columns)
```
┌─────────────────┬─────────────────┬─────────────────┐
│ SOURCES         │ STILLS          │ TOP PERFORMERS  │
│ NEEDING REVIEW  │ NEEDING         │                 │
│                 │ ATTENTION       │                 │
│ • Source A      │ • 5 expired     │ • Best stat     │
│   (14 days ago) │ • 8 needs_review│ • Best quote    │
│ • Source B      │ • 3 never used  │ • Most used     │
│   (review due)  │ • 2 low perf    │                 │
└─────────────────┴─────────────────┴─────────────────┘
         [ Bulk Actions Bar ]
```

---

## 2. API Endpoints

### New Router: `/app/api/refresh.py`

```python
# Core dashboard data
GET  /api/refresh/dashboard           # Returns all counts and lists for the 3 columns
GET  /api/refresh/sources-needing-review   # Sources with review_date passed/approaching
GET  /api/refresh/stills-needing-attention # Grouped by reason
GET  /api/refresh/top-performers      # High usage + high performance stills

# Bulk actions
POST /api/refresh/bulk-retire         # { still_ids: [...] }
POST /api/refresh/bulk-extend-review  # { source_ids: [...], days: 180 }
GET  /api/refresh/export-stale        # Returns CSV of stale content

# Source refresh workflow
POST /api/refresh/start-refresh       # { source_id, new_content } → starts refresh job
GET  /api/refresh/diff/{job_id}       # Returns diff view data
POST /api/refresh/apply-merge         # { job_id, actions: [...] }

# Notification counts (lightweight)
GET  /api/refresh/counts              # { sources: 3, stills: 12 }

# Performance tracking
GET  /api/stills/{id}/outputs         # Get outputs that used this still
POST /api/outputs/{id}/mark-performer # { still_ids: [...] }
```

---

## 3. Source Refresh Workflow (Diff/Merge)

### Flow
1. User clicks "Refresh Source" on a source card
2. Modal opens: "Upload new version or paste content"
3. System runs Source of Truth + Distillation on new content (temporary stills)
4. Diff View opens showing three categories

### Diff View UI
```
┌─────────────────────────────────────────────────────────┐
│ REFRESH: "Q3 2024 Report" → "Q4 2024 Report"           │
├─────────────────────────────────────────────────────────┤
│ 🔄 MATCHED (3)              Action                      │
│ ├─ "ROI improved 40%"   →  "ROI improved 52%"  [Merge] │
│ ├─ "3 key challenges"   →  "3 key challenges"  [Keep]  │
│ └─ "CEO quote about..."  →  "CEO quote about..." [Merge]│
├─────────────────────────────────────────────────────────┤
│ ✨ NEW (5)                  Action                      │
│ ├─ "New market expansion data"              [Add]      │
│ └─ "Customer story: Acme Corp"              [Add]      │
├─────────────────────────────────────────────────────────┤
│ 🗑️ ORPHANED (2)             Action                      │
│ ├─ "Q3 specific projection"                 [Retire]   │
│ └─ "Old partnership mention"                [Retire]   │
└─────────────────────────────────────────────────────────┘

[ Cancel ]                              [ Apply Changes ]
```

### Matching Logic (`/app/services/still_matcher.py`)

```python
async def match_stills(old_stills, new_stills, user_id):
    matches = []
    for new_still in new_stills:
        # Step 1: Fuzzy match (fast)
        best_match, score = fuzzy_match(new_still, old_stills)

        if score > 0.85:  # High confidence
            matches.append({"old": best_match, "new": new_still, "confidence": "high"})
        elif score > 0.5:  # Uncertain - use LLM
            llm_result = await llm_match(new_still, old_stills, user_id)
            matches.append(llm_result)
        else:  # No match - it's new
            matches.append({"old": None, "new": new_still, "confidence": "new"})

    # Find orphans (old stills with no match)
    matched_old_ids = {m["old"]["id"] for m in matches if m["old"]}
    orphans = [s for s in old_stills if s["id"] not in matched_old_ids]

    return matches, orphans
```

### Merge Actions
| Action | Effect |
|--------|--------|
| Merge | Update old still's content with new, preserve usage_count, last_used_at, performance |
| Add | Create new still, link to source |
| Retire | Set old still's status = "retired" |
| Keep | Do nothing (old still stays as-is) |

---

## 4. Automatic Status Updates

### Service: `/app/services/refresh_tasks.py`

```python
async def run_refresh_maintenance(user_id: int = None) -> dict:
    """
    Run all automatic status updates. Triggered via:
    - Admin endpoint: POST /admin/api/run-refresh-maintenance
    - Manually from Refresh Dashboard
    """
    results = {
        "stills_marked_needs_review": 0,
        "stills_retired": 0,
        "sources_flagged": 0,
    }

    # 1. Mark stills expiring within 30 days as needs_review
    # 2. Auto-retire stills past expiration_date
    # 3. Flag sources where review_date has passed

    return results
```

### Behavior Notes
- Stills with `expiration_type = "evergreen"` are never auto-retired
- Auto-retire only sets `status = "retired"`, never deletes data
- Sources are flagged for review but user must manually confirm

---

## 5. Performance Tracking UI

### Still Detail View (in Reserve)
```
┌─────────────────────────────────────────────────────────┐
│ STILL DETAIL                                      [X]   │
├─────────────────────────────────────────────────────────┤
│ "Companies that prioritize customer experience see     │
│  40% higher revenue growth."                           │
│                                                        │
│ Type: DATA          Status: [Active ▼]                 │
│ Funnel: Awareness   Performance: [Medium ▼]            │
│ Expiration: 2025-03-15 (date_bound)                    │
├─────────────────────────────────────────────────────────┤
│ 📊 USAGE STATS                                         │
│ Used 12 times · Last used: Jan 2, 2025                │
├─────────────────────────────────────────────────────────┤
│ 📝 OUTPUTS USING THIS STILL                            │
│ • LinkedIn post (Dec 28) - "Customer Experience..."    │
│ • Blog post (Dec 15) - "The ROI of CX Investment"      │
│ • Email (Dec 10) - "Quick insight for you"             │
├─────────────────────────────────────────────────────────┤
│ 📚 SOURCE CONTEXT                                      │
│ From: "Q4 Customer Report"                             │
│ Core Narrative: "CX drives measurable business value"  │
│ The Promise: "Better CX = Better Revenue"              │
└─────────────────────────────────────────────────────────┘
```

### High Performer Prompt (in Outputs view)
When user clicks "Mark as High Performer" on an output:
```
┌─────────────────────────────────────────────────────────┐
│ 🏆 MARK AS HIGH PERFORMER                               │
├─────────────────────────────────────────────────────────┤
│ This output used 4 stills. Which ones contributed      │
│ to its success?                                        │
│                                                        │
│ ☑ "40% higher revenue growth" (DATA)                   │
│ ☐ "Companies struggle with..." (PROBLEM)               │
│ ☑ "The key is measuring what matters" (INSIGHT)        │
│ ☐ "Start with your best customers" (SOLUTION)          │
│                                                        │
│ [ Cancel ]                    [ Mark Selected as High ] │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Bulk Actions

### Actions Bar (bottom of Refresh Dashboard)
```
┌─────────────────────────────────────────────────────────────────┐
│ ☑ 8 items selected                                              │
│                                                                 │
│ [Retire All Expired]  [Extend Review +6mo]  [Export CSV]        │
└─────────────────────────────────────────────────────────────────┘
```

### Action Behaviors
| Action | Scope | Effect |
|--------|-------|--------|
| Retire All Expired | Stills with expiration_date < today | Sets status = "retired" |
| Extend Review +6mo | Selected sources | Adds 180 days to review_date |
| Export CSV | All stills needing attention | Downloads CSV |

### CSV Export Format
```csv
id,content,type,status,reason,expiration_date,usage_count,performance,source
abc123,"40% revenue growth",data,needs_review,expiring_soon,2025-01-15,12,high,"Q4 Report"
```

---

## 7. Admin Panel Additions

### New Prompt Template: `still_matching`
Location: `/data/prompts/still_matching.txt`

```
You are comparing content stills to find matches between an old source and a new version.

OLD STILL:
{old_still_content}
Type: {old_still_type}

NEW STILL CANDIDATES:
{new_still_candidates}

SOURCE CONTEXT:
{source_context}

Determine if any of the new still candidates are an updated version of the old still.

OUTPUT FORMAT (valid JSON):
{
  "match_found": true/false,
  "matched_candidate_index": 0,
  "confidence": "high" | "medium" | "low",
  "reasoning": "Brief explanation"
}
```

### New Admin Settings
```
┌─────────────────────────────────────────────────────────┐
│ REFRESH SETTINGS                                        │
├─────────────────────────────────────────────────────────┤
│ Still Matching Model: [google/gemini-flash-1.5 ▼]      │
│ Fuzzy Match Threshold (high): [0.85]                   │
│ Fuzzy Match Threshold (uncertain): [0.50]              │
│ Auto-retire expired stills: [✓] Enabled                │
│ Days before expiration to flag: [30]                   │
└─────────────────────────────────────────────────────────┘
```

### Database Settings Entries
```sql
INSERT INTO settings (key, value) VALUES
  ('still_matching_model', 'google/gemini-flash-1.5'),
  ('fuzzy_match_high_threshold', '0.85'),
  ('fuzzy_match_low_threshold', '0.50'),
  ('auto_retire_expired', 'true'),
  ('expiration_warning_days', '30');
```

---

## Implementation Order

1. **API Layer** - `/app/api/refresh.py` with core endpoints
2. **Refresh Tasks Service** - `/app/services/refresh_tasks.py` for maintenance
3. **Dashboard Page** - `/frontend/refresh.html` with three-column layout
4. **Nav Badge** - Update `components.js` to show notification counts
5. **Still Matcher** - `/app/services/still_matcher.py` with hybrid logic
6. **Source Refresh Flow** - Upload, diff view, merge workflow
7. **Performance Tracking** - Still detail view enhancements, output marking
8. **Bulk Actions** - Retire, extend, export functionality
9. **Admin Settings** - Prompt template, model selection, thresholds

---

## Success Criteria

- Users can see what content needs attention at a glance
- Stale content is automatically flagged
- Performance data is tracked and visible
- Users can efficiently refresh/retire content in bulk
- Source refresh preserves usage history through smart merging
