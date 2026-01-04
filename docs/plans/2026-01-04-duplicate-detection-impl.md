# Duplicate Detection Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Find Duplicates" button to the refresh page that scans for similar stills and allows users to merge them.

**Architecture:** On-demand duplicate scanning using existing `calculate_similarity()` function from library_manager.py. Results stored in memory (not database) and displayed in "Stills Needing Attention" section. Side-by-side comparison modal for user-controlled merge decisions. Losing still is retired (not deleted).

**Tech Stack:** Python/FastAPI backend, vanilla JavaScript frontend, Pydantic models, pytest for testing.

---

## Task 1: Add Pydantic Models

**Files:**
- Modify: `app/models/refresh.py`

**Step 1: Add request/response models**

```python
# Add to app/models/refresh.py after existing models

class MergeDuplicatesRequest(BaseModel):
    winner_id: str
    loser_id: str


class DuplicatePair(BaseModel):
    still_a: dict
    still_b: dict
    similarity: float


class FindDuplicatesResponse(BaseModel):
    duplicates: List[DuplicatePair]
    threshold_used: float
    stills_scanned: int
```

**Step 2: Run type check**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -c "from app.models.refresh import MergeDuplicatesRequest, FindDuplicatesResponse; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/models/refresh.py
git commit -m "feat(refresh): add Pydantic models for duplicate detection"
```

---

## Task 2: Add Service Functions (with tests)

**Files:**
- Modify: `app/services/refresh_tasks.py`
- Modify: `tests/test_refresh_tasks.py`

**Step 1: Write failing test for find_duplicate_stills**

Add to `tests/test_refresh_tasks.py`:

```python
from app.services.refresh_tasks import find_duplicate_stills, merge_duplicate_stills


@pytest.mark.asyncio
async def test_find_duplicate_stills_empty(test_db):
    """Returns empty list when no stills exist."""
    result = await find_duplicate_stills(user_id=1)
    assert result["duplicates"] == []
    assert result["threshold_used"] == 0.90
    assert result["stills_scanned"] == 0


@pytest.mark.asyncio
async def test_find_duplicate_stills_no_duplicates(test_db):
    """Returns empty list when stills are unique."""
    # Insert two very different stills
    from app.database import get_db
    from app.db_utils import execute
    import uuid

    async with get_db() as db:
        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), "job1", 1, "insight", "This is about marketing strategies", "active"))

        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), "job1", 1, "insight", "Completely different topic about cooking", "active"))

        await db.commit()

    result = await find_duplicate_stills(user_id=1)
    assert result["duplicates"] == []
    assert result["stills_scanned"] == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/test_refresh_tasks.py::test_find_duplicate_stills_empty -v`
Expected: FAIL with "cannot import name 'find_duplicate_stills'"

**Step 3: Implement find_duplicate_stills**

Add to `app/services/refresh_tasks.py` (add import at top):

```python
# Add to imports at top
from app.services.library_manager import calculate_similarity
from app.services.settings_manager import get_global_setting
```

```python
# Add after existing functions

async def find_duplicate_stills(user_id: int) -> dict:
    """
    Find duplicate stills in user's library.

    Returns dict with:
    - duplicates: list of {still_a, still_b, similarity} dicts
    - threshold_used: float
    - stills_scanned: int
    """
    threshold = float(await get_global_setting('duplicate_similarity_threshold', '0.90'))

    result = {
        "duplicates": [],
        "threshold_used": threshold,
        "stills_scanned": 0
    }

    async with get_db() as db:
        # Get all active stills for user
        rows = await fetchall(db, """
            SELECT id, content, still_type, usage_count, performance, status,
                   created_at, source_file, job_id
            FROM stills
            WHERE user_id = ? AND status = 'active'
            ORDER BY still_type, created_at
        """, (user_id,))

        stills = [dict(r) for r in rows]
        result["stills_scanned"] = len(stills)

        if len(stills) < 2:
            return result

        # Group by still_type for efficient comparison
        by_type = {}
        for still in stills:
            st = still["still_type"]
            if st not in by_type:
                by_type[st] = []
            by_type[st].append(still)

        # Compare within each type group
        seen_pairs = set()
        for still_type, group in by_type.items():
            for i, still_a in enumerate(group):
                for still_b in group[i+1:]:
                    # Create consistent pair key to avoid duplicates
                    pair_key = tuple(sorted([still_a["id"], still_b["id"]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Calculate similarity
                    score = calculate_similarity(
                        still_a.get("content", ""),
                        still_b.get("content", "")
                    )

                    if score >= threshold:
                        result["duplicates"].append({
                            "still_a": still_a,
                            "still_b": still_b,
                            "similarity": round(score, 3)
                        })

        # Sort by similarity descending
        result["duplicates"].sort(key=lambda x: x["similarity"], reverse=True)

    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/test_refresh_tasks.py -v -k "duplicate"`
Expected: PASS

**Step 5: Write test for merge_duplicate_stills**

Add to `tests/test_refresh_tasks.py`:

```python
@pytest.mark.asyncio
async def test_merge_duplicate_stills(test_db):
    """Merge retires the loser still."""
    from app.database import get_db
    from app.db_utils import execute, fetchone
    import uuid

    winner_id = str(uuid.uuid4())
    loser_id = str(uuid.uuid4())

    async with get_db() as db:
        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (winner_id, "job1", 1, "insight", "Winner content", "active"))

        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (loser_id, "job1", 1, "insight", "Loser content", "active"))

        await db.commit()

    result = await merge_duplicate_stills(winner_id, loser_id, user_id=1)
    assert result["success"] == True
    assert result["retired_still_id"] == loser_id

    # Verify loser is retired
    async with get_db() as db:
        loser = await fetchone(db, "SELECT status FROM stills WHERE id = ?", (loser_id,))
        assert loser["status"] == "retired"

        winner = await fetchone(db, "SELECT status FROM stills WHERE id = ?", (winner_id,))
        assert winner["status"] == "active"
```

**Step 6: Run test to verify it fails**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/test_refresh_tasks.py::test_merge_duplicate_stills -v`
Expected: FAIL

**Step 7: Implement merge_duplicate_stills**

Add to `app/services/refresh_tasks.py`:

```python
async def merge_duplicate_stills(winner_id: str, loser_id: str, user_id: int) -> dict:
    """
    Retire the loser still, keeping the winner active.

    Returns dict with:
    - success: bool
    - retired_still_id: str
    - error: str (if failed)
    """
    from app.config import get_settings
    settings = get_settings()

    async with get_db() as db:
        # Verify both stills belong to user and are active
        winner = await fetchone(db,
            "SELECT id, status FROM stills WHERE id = ? AND user_id = ?",
            (winner_id, user_id)
        )
        loser = await fetchone(db,
            "SELECT id, status FROM stills WHERE id = ? AND user_id = ?",
            (loser_id, user_id)
        )

        if not winner:
            return {"success": False, "error": "Winner still not found"}
        if not loser:
            return {"success": False, "error": "Loser still not found"}
        if loser["status"] == "retired":
            return {"success": False, "error": "Still already retired"}

        # Retire the loser
        await execute(db,
            "UPDATE stills SET status = 'retired' WHERE id = ?",
            (loser_id,)
        )

        if not settings.use_postgres:
            await db.commit()

    return {
        "success": True,
        "retired_still_id": loser_id
    }
```

**Step 8: Run all duplicate tests**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/test_refresh_tasks.py -v -k "duplicate"`
Expected: All PASS

**Step 9: Commit**

```bash
git add app/services/refresh_tasks.py tests/test_refresh_tasks.py
git commit -m "feat(refresh): add find_duplicate_stills and merge_duplicate_stills functions"
```

---

## Task 3: Add API Endpoints

**Files:**
- Modify: `app/api/refresh.py`

**Step 1: Add imports and endpoints**

Add to imports at top of `app/api/refresh.py`:

```python
from app.models.refresh import (
    BulkRetireRequest,
    BulkExtendReviewRequest,
    MarkPerformerRequest,
    RefreshCounts,
    MergeDuplicatesRequest,  # Add this
)
from app.services.refresh_tasks import (
    get_stills_needing_attention,
    get_sources_needing_review,
    get_top_performers,
    get_refresh_counts,
    run_refresh_maintenance,
    find_duplicate_stills,      # Add this
    merge_duplicate_stills,     # Add this
)
```

Add endpoints after existing ones:

```python
@router.post("/refresh/find-duplicates")
async def find_duplicates(user_id: int = Depends(get_current_user_id)):
    """Scan for duplicate stills in user's library."""
    return await find_duplicate_stills(user_id)


@router.post("/refresh/merge-duplicates")
async def merge_duplicates(
    request: MergeDuplicatesRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Merge duplicate stills by retiring the loser."""
    result = await merge_duplicate_stills(request.winner_id, request.loser_id, user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Merge failed"))
    return result
```

**Step 2: Run basic import check**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -c "from app.api.refresh import router; print('OK')"`
Expected: OK

**Step 3: Run full test suite to ensure nothing broke**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/ --ignore=tests/test_e2e.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add app/api/refresh.py
git commit -m "feat(refresh): add find-duplicates and merge-duplicates API endpoints"
```

---

## Task 4: Add UI Button and Modal HTML

**Files:**
- Modify: `frontend/refresh.html`

**Step 1: Add button to header**

Find this line in `frontend/refresh.html`:

```html
<button id="run-maintenance-btn" class="btn btn-primary">
    Run Maintenance Check
</button>
```

Replace with:

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

**Step 2: Add comparison modal HTML**

Add before closing `</body>` tag in `frontend/refresh.html`:

```html
<!-- Duplicate Comparison Modal -->
<div id="duplicate-modal" class="hidden">
    <div class="modal-backdrop" onclick="closeDuplicateModal()"></div>
    <div class="modal" style="width: 95%; max-width: 900px;">
        <div class="p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-still-text">Merge Duplicates</h2>
                <button onclick="closeDuplicateModal()" class="text-still-muted hover:text-still-text">&times;</button>
            </div>
            <div id="duplicate-modal-body"></div>
        </div>
    </div>
</div>
```

**Step 3: Commit**

```bash
git add frontend/refresh.html
git commit -m "feat(refresh): add Find Duplicates button and comparison modal HTML"
```

---

## Task 5: Add JavaScript Functions

**Files:**
- Modify: `frontend/static/refresh.js`

**Step 1: Add duplicates category to renderStills**

Find this code in `renderStills()`:

```javascript
const categories = [
    { key: 'expired', label: 'Expired' },
    { key: 'needs_review', label: 'Needs Review' },
    { key: 'never_used', label: 'Never Used (30+ days)' },
    { key: 'low_performance', label: 'Low Performance' },
];
```

Replace with:

```javascript
const categories = [
    { key: 'duplicates', label: 'Duplicates Found', isDuplicate: true },
    { key: 'expired', label: 'Expired' },
    { key: 'needs_review', label: 'Needs Review' },
    { key: 'never_used', label: 'Never Used (30+ days)' },
    { key: 'low_performance', label: 'Low Performance' },
];
```

**Step 2: Update category rendering for duplicates**

Find and replace the category rendering loop in `renderStills()`:

```javascript
const html = categories.map(cat => {
    const items = stills[cat.key] || [];
    totalCount += items.length;

    if (items.length === 0) return '';

    // Special rendering for duplicates (pairs)
    if (cat.isDuplicate) {
        return `
            <div class="still-category mb-4">
                <h3 class="text-sm font-medium text-still-amber mb-2">
                    ${cat.label} (${items.length} pairs)
                </h3>
                <div class="space-y-2">
                    ${items.slice(0, 5).map((pair, idx) => `
                        <div class="duplicate-item p-2 bg-still-card rounded border border-still-amber/30 cursor-pointer hover:border-still-amber transition-colors"
                             onclick="showDuplicateComparison(${idx})">
                            <div class="flex justify-between items-center">
                                <p class="text-sm text-still-text truncate flex-1">${Utils.escapeHtml(pair.still_a.content.substring(0, 60))}...</p>
                                <span class="badge badge-amber text-xs ml-2">${Math.round(pair.similarity * 100)}%</span>
                            </div>
                        </div>
                    `).join('')}
                    ${items.length > 5 ? `<p class="text-xs text-still-muted">+${items.length - 5} more pairs</p>` : ''}
                </div>
            </div>
        `;
    }

    return `
        <div class="still-category mb-4">
            <h3 class="text-sm font-medium text-still-muted mb-2">
                ${cat.label} (${items.length})
            </h3>
            <div class="space-y-2">
                ${items.slice(0, 5).map(still => `
                    <div class="still-item p-2 bg-still-card rounded border border-still-border cursor-pointer hover:border-still-copper transition-colors"
                         onclick="showStillDetail('${still.id}')">
                        <p class="text-sm text-still-text truncate">${Utils.escapeHtml(still.content)}</p>
                        <p class="text-xs text-still-disabled">${Utils.escapeHtml(still.still_type)} - ${Utils.escapeHtml(still.source_name || 'Unknown source')}</p>
                    </div>
                `).join('')}
                ${items.length > 5 ? `<p class="text-xs text-still-muted">+${items.length - 5} more</p>` : ''}
            </div>
        </div>
    `;
}).join('');
```

**Step 3: Add event listener in setupEventListeners**

Find `setupEventListeners()` function and add:

```javascript
document.getElementById('find-duplicates-btn').addEventListener('click', findDuplicates);
```

**Step 4: Add findDuplicates function**

Add after `runMaintenance()` function:

```javascript
async function findDuplicates() {
    const btn = document.getElementById('find-duplicates-btn');
    const originalText = btn.textContent;
    btn.textContent = 'Scanning...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/refresh/find-duplicates', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        if (!response.ok) throw new Error('Scan failed');

        const data = await response.json();

        if (data.duplicates.length > 0) {
            // Add duplicates to dashboard data
            dashboardData.stills_needing_attention.duplicates = data.duplicates;
            renderStills();
            Utils.showToast(`Found ${data.duplicates.length} duplicate pairs (${data.stills_scanned} stills scanned)`, 'success');
        } else {
            Utils.showToast(`No duplicates found above ${Math.round(data.threshold_used * 100)}% similarity (${data.stills_scanned} stills scanned)`, 'info');
        }
    } catch (error) {
        console.error('Find duplicates error:', error);
        Utils.showToast('Failed to scan for duplicates', 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}
```

**Step 5: Add duplicate comparison modal functions**

Add at end of file:

```javascript
function showDuplicateComparison(pairIndex) {
    const pairs = dashboardData.stills_needing_attention.duplicates || [];
    if (pairIndex >= pairs.length) return;

    const pair = pairs[pairIndex];
    const modal = document.getElementById('duplicate-modal');
    const body = document.getElementById('duplicate-modal-body');

    body.innerHTML = `
        <p class="text-still-amber text-center mb-4 font-medium">${Math.round(pair.similarity * 100)}% similar</p>
        <div class="grid grid-cols-2 gap-4">
            <!-- Still A -->
            <div class="border border-still-border rounded-lg p-4">
                <h3 class="font-semibold text-still-text mb-3">Still A</h3>
                <div class="space-y-2 text-sm">
                    <p><span class="text-still-muted">Created:</span> <span class="text-still-text">${formatDate(pair.still_a.created_at)}</span></p>
                    <p><span class="text-still-muted">Type:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_a.still_type)}</span></p>
                    <p><span class="text-still-muted">Used:</span> <span class="text-still-text">${pair.still_a.usage_count || 0} times</span></p>
                    <p><span class="text-still-muted">Source:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_a.source_file || 'Unknown')}</span></p>
                </div>
                <div class="mt-4 p-3 bg-still-bg rounded text-still-text text-sm max-h-40 overflow-y-auto">
                    ${Utils.escapeHtml(pair.still_a.content)}
                </div>
                <button onclick="mergeDuplicates('${pair.still_a.id}', '${pair.still_b.id}', ${pairIndex})"
                        class="mt-4 w-full btn btn-primary">
                    Keep This One
                </button>
            </div>

            <!-- Still B -->
            <div class="border border-still-border rounded-lg p-4">
                <h3 class="font-semibold text-still-text mb-3">Still B</h3>
                <div class="space-y-2 text-sm">
                    <p><span class="text-still-muted">Created:</span> <span class="text-still-text">${formatDate(pair.still_b.created_at)}</span></p>
                    <p><span class="text-still-muted">Type:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_b.still_type)}</span></p>
                    <p><span class="text-still-muted">Used:</span> <span class="text-still-text">${pair.still_b.usage_count || 0} times</span></p>
                    <p><span class="text-still-muted">Source:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_b.source_file || 'Unknown')}</span></p>
                </div>
                <div class="mt-4 p-3 bg-still-bg rounded text-still-text text-sm max-h-40 overflow-y-auto">
                    ${Utils.escapeHtml(pair.still_b.content)}
                </div>
                <button onclick="mergeDuplicates('${pair.still_b.id}', '${pair.still_a.id}', ${pairIndex})"
                        class="mt-4 w-full btn btn-primary">
                    Keep This One
                </button>
            </div>
        </div>
        <div class="mt-4 text-center">
            <button onclick="skipDuplicate(${pairIndex})" class="btn btn-secondary">
                Skip - Not Duplicates
            </button>
        </div>
    `;

    modal.classList.remove('hidden');
}

function closeDuplicateModal() {
    document.getElementById('duplicate-modal').classList.add('hidden');
}

async function mergeDuplicates(winnerId, loserId, pairIndex) {
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

        // Remove pair from list
        dashboardData.stills_needing_attention.duplicates.splice(pairIndex, 1);

        // If no more duplicates, remove the category
        if (dashboardData.stills_needing_attention.duplicates.length === 0) {
            delete dashboardData.stills_needing_attention.duplicates;
        }

        renderStills();
        closeDuplicateModal();
        Utils.showToast('Merged - 1 still retired', 'success');
    } catch (error) {
        console.error('Merge error:', error);
        Utils.showToast(error.message || 'Failed to merge duplicates', 'error');
    }
}

function skipDuplicate(pairIndex) {
    // Just remove from current view without merging
    dashboardData.stills_needing_attention.duplicates.splice(pairIndex, 1);

    if (dashboardData.stills_needing_attention.duplicates.length === 0) {
        delete dashboardData.stills_needing_attention.duplicates;
    }

    renderStills();
    closeDuplicateModal();
    Utils.showToast('Skipped - pair removed from list', 'info');
}
```

**Step 6: Run full test suite**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/ --ignore=tests/test_e2e.py -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add frontend/static/refresh.js
git commit -m "feat(refresh): add JavaScript for duplicate scanning and merging"
```

---

## Task 6: Final Testing and Push

**Step 1: Run full test suite**

Run: `cd /Users/treynortetik/Documents/Still\ Local\ Repo/Still && python3 -m pytest tests/ --ignore=tests/test_e2e.py -v`
Expected: All tests pass

**Step 2: Push all commits**

```bash
git push
```

---

## Summary

| Task | Description | Est. Steps |
|------|-------------|------------|
| 1 | Add Pydantic models | 3 |
| 2 | Add service functions with tests | 9 |
| 3 | Add API endpoints | 4 |
| 4 | Add UI button and modal HTML | 3 |
| 5 | Add JavaScript functions | 7 |
| 6 | Final testing and push | 2 |

**Total:** 28 steps
