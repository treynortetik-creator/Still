# Source of Truth UX Improvements

**Date:** 2026-01-04
**Status:** Approved

## Problem Statement

1. After approving Source of Truth, users see an "Approved" badge but have no visibility into the continuing pipeline (distillation, drafting, etc.)
2. No way to view/edit Source of Truth documents from the Library - must navigate to specific job results

## Solution Overview

### Feature 1: Split View After SOT Approval

Transform results page into a split-view layout after Source of Truth approval, showing:
- Left panel: Approved SOT (read-only reference)
- Right panel: Live processing status with step-by-step progress

### Feature 2: Library SOT Access

Add [SOT] button to each library row that opens a modal for viewing/editing Source of Truth documents.

---

## Detailed Design

### Split View Architecture

**Layout:**
```
+-------------------------------------------------------------+
|  [Header: Job Title]                                        |
+----------------------------+--------------------------------+
|                            |                                |
|   SOURCE OF TRUTH          |   PROCESSING STATUS            |
|   (Current content)        |                                |
|                            |   * Distilling content... 45%  |
|   - Core Narratives        |   o Drafting LinkedIn posts    |
|   - Statistics             |   o Creating blog posts        |
|   - Quotable Moments       |   o Fact-checking              |
|   - Pain Point             |   o Quality scoring            |
|   - Promise                |                                |
|   - etc.                   |   [Live progress updates]      |
|                            |                                |
|   Approved                 |                                |
|                            |                                |
+----------------------------+--------------------------------+
|  [Footer / Actions]                                         |
+-------------------------------------------------------------+
```

**Behavior:**
- Left panel: Read-only SOT display (already approved)
- Right panel: Live status polling from `/api/jobs/{id}/status` every 3 seconds
- When complete: Right panel shows "Complete!" with link to view outputs
- Responsive: On mobile, stack vertically (SOT on top, status below)

### Library SOT Modal

**Table Enhancement:**
```
+----------------------------------------------------------------------+
| Title          | Type   | Date       | Status    | Actions          |
+----------------------------------------------------------------------+
| Q4 Keynote     | Video  | 2024-01-03 | Complete  | [SOT] [View] [...] |
| Product Demo   | Audio  | 2024-01-02 | Complete  | [SOT] [View] [...] |
| Blog Draft     | Text   | 2024-01-01 | Processing| [--]  [View] [...] |
+----------------------------------------------------------------------+
```

**SOT Button States:**
- `[SOT]` (blue) - Has approved Source of Truth, click to view/edit
- `[SOT]` (amber) - Has SOT pending approval, click to review
- `[--]` (gray/disabled) - No SOT yet (still processing or quick distill without SOT)

**Modal Design:**
```
+-------------------------------------------------------------+
|  Source of Truth: "Q4 Keynote"              [Edit] [X]      |
+-------------------------------------------------------------+
|                                                             |
|  Status: Approved (Jan 3, 2024)                             |
|  Review Date: Jul 3, 2024                                   |
|                                                             |
|  ---------------------------------------------------------  |
|  CORE NARRATIVES                                            |
|  * Narrative 1 with supporting evidence...                  |
|  * Narrative 2 with supporting evidence...                  |
|                                                             |
|  STATISTICS                                                 |
|  | Stat | Citation | Expires | Confidence |                 |
|                                                             |
|  [... rest of SOT sections ...]                             |
|                                                             |
+-------------------------------------------------------------+
|                              [Close]  [Save Changes]        |
+-------------------------------------------------------------+
```

**Edit Mode:** Click "Edit" to toggle fields to editable inputs. Save persists via `PUT /api/jobs/{job_id}/source`.

---

## Data Flow

### Split View Flow

```
User clicks "Approve & Continue"
         |
POST /api/jobs/{id}/approve-source
         |
Backend: mark approved, launch resume_pipeline_from_distillation()
         |
Response: { status: "approved", job_status: "processing" }
         |
Frontend: Switch to split-view layout
         |
Start polling GET /api/jobs/{id}/status every 3 seconds
         |
Update right panel with current step/progress
         |
When status === "complete": Show completion state, link to outputs
```

### Library Modal Flow

```
User clicks [SOT] button on library row
         |
GET /api/jobs/{job_id}/source
         |
Populate modal with SOT data
         |
User edits fields, clicks "Save Changes"
         |
PUT /api/jobs/{job_id}/source (with updated fields)
         |
Show success toast, close modal or stay open
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Pipeline fails mid-processing | Right panel shows error message with retry option |
| SOT fetch fails (404) | Modal shows "No Source of Truth found" with link to job |
| SOT save fails | Toast error, keep modal open, don't lose edits |
| Network disconnect during polling | Show "Reconnecting..." badge, resume when back |
| Job deleted while viewing | Modal closes, toast "This job no longer exists" |

---

## Edge Cases

- Entry without SOT (quick distill, processing): Button disabled/grayed
- SOT pending approval from Library: Opens modal with approve option
- Multiple tabs: Polling handles stale state gracefully

---

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/results.html` | Add split view layout, polling logic, conditional rendering |
| `frontend/library.html` | Add SOT column, modal component, edit functionality |
| `frontend/css/` (if separate) | Styling for split view and modal |

**No backend changes needed** - existing endpoints cover all functionality:
- `GET /api/jobs/{id}/status` - polling
- `GET /api/jobs/{job_id}/source` - fetch SOT
- `PUT /api/jobs/{job_id}/source` - update SOT
- `POST /api/jobs/{id}/approve-source` - approve SOT

---

## Implementation Order

1. Split View on results.html (higher priority - fixes the immediate UX gap)
2. Library SOT modal (enhancement for accessing existing SOTs)
