# Campaign Tagging & Auto-Generated Topics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make campaign name mandatory for full pipeline, add campaign_name + topics columns to stills/outputs for denormalized filtering, and enhance Reserve with topic-based search.

**Architecture:**
- Add `campaign_name` and `topics` (JSON array) columns to both `stills` and `outputs` tables
- Modify distillation to extract 2-3 topic keywords per still
- Update all storage functions to propagate campaign_name and topics
- Add campaign and topic filter dropdowns to Reserve UI

**Tech Stack:** SQLite, FastAPI, Pydantic, vanilla JS, TailwindCSS

---

## Task 1: Database Migration - Add campaign_name and topics columns

**Files:**
- Modify: `app/database.py`

**Step 1: Add migration function for stills table**

In `app/database.py`, add this migration after the existing migrations (around line 540):

```python
async def migrate_add_campaign_and_topics():
    """Add campaign_name and topics columns to stills and outputs tables."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if columns exist on stills
        cursor = await db.execute("PRAGMA table_info(stills)")
        stills_cols = [row[1] for row in await cursor.fetchall()]

        if "campaign_name" not in stills_cols:
            await db.execute("ALTER TABLE stills ADD COLUMN campaign_name TEXT")
            print("Added campaign_name column to stills")

        if "topics" not in stills_cols:
            await db.execute("ALTER TABLE stills ADD COLUMN topics JSON")
            print("Added topics column to stills")

        # Check if columns exist on outputs
        cursor = await db.execute("PRAGMA table_info(outputs)")
        outputs_cols = [row[1] for row in await cursor.fetchall()]

        if "campaign_name" not in outputs_cols:
            await db.execute("ALTER TABLE outputs ADD COLUMN campaign_name TEXT")
            print("Added campaign_name column to outputs")

        if "topics" not in outputs_cols:
            await db.execute("ALTER TABLE outputs ADD COLUMN topics JSON")
            print("Added topics column to outputs")

        # Check if columns exist on content_library
        cursor = await db.execute("PRAGMA table_info(content_library)")
        library_cols = [row[1] for row in await cursor.fetchall()]

        if "campaign_name" not in library_cols:
            await db.execute("ALTER TABLE content_library ADD COLUMN campaign_name TEXT")
            print("Added campaign_name column to content_library")

        if "topics" not in library_cols:
            await db.execute("ALTER TABLE content_library ADD COLUMN topics_extracted JSON")
            print("Added topics_extracted column to content_library")

        await db.commit()
```

**Step 2: Call migration in init_db**

In `init_db()` function, add at the end before the final commit:

```python
        # Run new migrations
        await migrate_add_campaign_and_topics()
```

**Step 3: Restart server to verify migration runs**

Run: `pkill -f uvicorn && uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload`
Expected: Console shows "Added campaign_name column to stills", etc.

**Step 4: Commit**

```bash
git add app/database.py
git commit -m "feat: add campaign_name and topics columns to stills/outputs tables"
```

---

## Task 2: Update distillation to extract topics

**Files:**
- Modify: `app/services/distillation.py`

**Step 1: Update the LLM prompt to extract topics**

In `distill_content()`, update the `full_prompt` section to include topics extraction:

```python
    full_prompt = prompt + """

IMPORTANT - EXTRACT QUOTES:
Look for memorable, impactful direct quotes from speakers in the source material.
These are exact words someone said that could be used in content like:
"As [Speaker] said: '...'" or as a pull quote.
Include the speaker/attribution when available.

IMPORTANT - EXTRACT TOPICS:
For each still, identify 2-3 topic keywords that describe what this still is about.
Topics should be lowercase, single words or short phrases (max 2 words).
Examples: "leadership", "roi", "patient safety", "staff retention", "technology"

OUTPUT FORMAT:
Return valid JSON with this structure:
{
  "stills": [
    {
      "type": "data|insight|story|problem|solution|quote",
      "content": "The actual content extracted (for quotes, use the exact verbatim text)",
      "source_location": "timestamp or section reference",
      "relevance_to_persona": 1-5,
      "why_relevant": "Brief explanation",
      "tags": ["tag1", "tag2"],
      "topics": ["topic1", "topic2"],
      "speaker": "Name of person who said this (for quotes only, null otherwise)"
    }
  ],
  "summary": "Brief summary of what was extracted",
  "recommended_distribution": {
    "linkedin": ["still indexes best for LinkedIn"],
    "blog": ["still indexes best for blog"],
    "email": ["still indexes best for email"]
  }
}"""
```

**Step 2: Update still processing to include topics**

In the `for still_data in still_data_list:` loop, update the still dict:

```python
        still = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "user_id": user_id,
            "still_type": still_data.get("type", "insight"),
            "content": still_data.get("content", ""),
            "source_location": still_data.get("source_location"),
            "tags": still_data.get("tags", []),
            "topics": still_data.get("topics", []),  # NEW: extract topics
            "persona_relevance": {
                relevance_key: still_data.get("relevance_to_persona", 3)
            },
            "why_relevant": still_data.get("why_relevant"),
            "quote_attribution": still_data.get("speaker"),
        }
```

**Step 3: Verify by running a test distillation**

Run: `python -c "print('Distillation updated')"`
Expected: No syntax errors

**Step 4: Commit**

```bash
git add app/services/distillation.py
git commit -m "feat: extract 2-3 topic keywords per still during distillation"
```

---

## Task 3: Update library_manager to save campaign_name and topics

**Files:**
- Modify: `app/services/library_manager.py`

**Step 1: Update validate_still to include new fields**

```python
def validate_still(still: dict) -> dict:
    """
    Validate and sanitize a still before database insertion.
    """
    return {
        "id": str(still.get("id", "")) if still.get("id") else None,
        "job_id": str(still.get("job_id", "")) if still.get("job_id") else None,
        "user_id": int(still.get("user_id", 0)) if still.get("user_id") else None,
        "still_type": str(still.get("still_type", "insight"))[:50],
        "content": str(still.get("content", ""))[:50000],
        "source_location": str(still.get("source_location", ""))[:500] if still.get("source_location") else None,
        "source_file": str(still.get("source_file", ""))[:500] if still.get("source_file") else None,
        "tags": still.get("tags") if isinstance(still.get("tags"), list) else [],
        "topics": still.get("topics") if isinstance(still.get("topics"), list) else [],  # NEW
        "campaign_name": str(still.get("campaign_name", ""))[:200] if still.get("campaign_name") else None,  # NEW
        "persona_relevance": still.get("persona_relevance") if isinstance(still.get("persona_relevance"), dict) else {},
        "quote_attribution": str(still.get("quote_attribution", ""))[:200] if still.get("quote_attribution") else None,
    }
```

**Step 2: Update add_stills_to_library function signature and INSERT**

```python
async def add_stills_to_library(
    stills: list[dict],
    user_id: int,
    source_file: Optional[str] = None,
    campaign_name: Optional[str] = None,  # NEW parameter
) -> int:
    """
    Add extracted stills to the Reserve (content library).
    """
    async with get_db() as db:
        count = 0

        for still in stills:
            validated = validate_still(still)
            # Use passed campaign_name or fall back to still's campaign_name
            final_campaign = campaign_name or validated["campaign_name"]

            await db.execute(
                """
                INSERT INTO content_library (
                    user_id, entry_type, content, source, source_timestamp,
                    tags, persona_relevance, campaign_name, topics_extracted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    validated["still_type"],
                    validated["content"],
                    source_file or validated["source_file"],
                    validated["source_location"],
                    json.dumps(validated["tags"]),
                    json.dumps(validated["persona_relevance"]),
                    final_campaign,  # NEW
                    json.dumps(validated["topics"]),  # NEW
                )
            )
            count += 1

        await db.commit()

    return count
```

**Step 3: Update save_stills_to_db INSERT**

```python
async def save_stills_to_db(stills: list[dict], campaign_name: Optional[str] = None) -> int:
    """
    Save stills to the stills table (job-specific tracking).
    """
    async with get_db() as db:
        count = 0

        for still in stills:
            validated = validate_still(still)

            if not validated["id"] or not validated["job_id"] or not validated["user_id"]:
                logger.warning(f"Skipping still with missing required fields: {still.get('id')}")
                continue

            final_campaign = campaign_name or validated["campaign_name"]

            await db.execute(
                """
                INSERT INTO stills (
                    id, job_id, user_id, still_type, content,
                    source_location, source_file, tags, persona_relevance,
                    quote_attribution, campaign_name, topics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validated["id"],
                    validated["job_id"],
                    validated["user_id"],
                    validated["still_type"],
                    validated["content"],
                    validated["source_location"],
                    validated["source_file"],
                    json.dumps(validated["tags"]),
                    json.dumps(validated["persona_relevance"]),
                    validated["quote_attribution"],
                    final_campaign,  # NEW
                    json.dumps(validated["topics"]),  # NEW
                )
            )
            count += 1

        await db.commit()

    return count
```

**Step 4: Update validate_output for campaign_name**

```python
def validate_output(output: dict) -> dict:
    """Validate and sanitize an output before database insertion."""
    return {
        "content_type": str(output.get("content_type", ""))[:50],
        "variation_number": int(output.get("variation_number", 1)) if output.get("variation_number") else 1,
        "content": str(output.get("content", "")) if output.get("content") else None,
        "step1_draft": str(output.get("step1_draft", "")) if output.get("step1_draft") else None,
        "step2_edited": str(output.get("step2_edited", "")) if output.get("step2_edited") else None,
        "step3_final": str(output.get("step3_final", "")) if output.get("step3_final") else None,
        "stills_used": output.get("stills_used", output.get("atoms_used", [])) if isinstance(output.get("stills_used", output.get("atoms_used")), list) else [],
        "citations": output.get("citations") if isinstance(output.get("citations"), list) else [],
        "warnings": output.get("warnings") if isinstance(output.get("warnings"), list) else [],
        "quality_scores": output.get("quality_scores") if isinstance(output.get("quality_scores"), dict) else None,
        "hook_variations": output.get("hook_variations") if isinstance(output.get("hook_variations"), list) else None,
        "subject": str(output.get("subject", ""))[:500] if output.get("subject") else None,
        "preview_text": str(output.get("preview_text", ""))[:500] if output.get("preview_text") else None,
        "email_day": int(output.get("email_day")) if output.get("email_day") and str(output.get("email_day")).isdigit() else None,
        "email_purpose": str(output.get("email_purpose", ""))[:200] if output.get("email_purpose") else None,
        "sequence_name": str(output.get("sequence_name", ""))[:200] if output.get("sequence_name") else None,
        "campaign_name": str(output.get("campaign_name", ""))[:200] if output.get("campaign_name") else None,  # NEW
    }
```

**Step 5: Update save_outputs_to_db to include campaign_name**

```python
async def save_outputs_to_db(outputs: list[dict], job_id: str, campaign_name: Optional[str] = None) -> int:
    """Save generated outputs to the database."""
    async with get_db() as db:
        count = 0

        for output in outputs:
            validated = validate_output(output)
            final_campaign = campaign_name or validated["campaign_name"]

            cursor = await db.execute(
                """
                INSERT INTO outputs (
                    job_id, content_type, variation_number,
                    step1_draft, step2_edited, step3_final,
                    atoms_used, citations, warnings, quality_scores,
                    hook_variations, subject, preview_text,
                    email_day, email_purpose, sequence_name, campaign_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    validated["content_type"],
                    validated["variation_number"],
                    validated["content"] or validated["step1_draft"],
                    validated["step2_edited"],
                    validated["step3_final"],
                    json.dumps(validated["stills_used"]),
                    json.dumps(validated["citations"]),
                    json.dumps(validated["warnings"]),
                    json.dumps(validated["quality_scores"]) if validated["quality_scores"] else None,
                    json.dumps(validated["hook_variations"]) if validated["hook_variations"] else None,
                    validated["subject"],
                    validated["preview_text"],
                    validated["email_day"],
                    validated["email_purpose"],
                    validated["sequence_name"],
                    final_campaign,  # NEW
                )
            )
            count += 1

        await db.commit()

    return count
```

**Step 6: Commit**

```bash
git add app/services/library_manager.py
git commit -m "feat: propagate campaign_name and topics through storage functions"
```

---

## Task 4: Update pipeline.py to pass campaign_name

**Files:**
- Modify: `app/services/pipeline.py`

**Step 1: Get campaign_name from job_data and pass to storage functions**

In `process_job()`, after getting job_data, extract campaign_name:

```python
        # Extract job parameters
        original_filename = job_data.get("original_filename", "unknown")
        target_persona = job_data.get("target_persona")
        asset_types = json.loads(job_data.get("asset_types", "[]"))
        asset_quantities = json.loads(job_data.get("asset_quantities", "{}"))
        campaign_name = job_data.get("campaign_name")  # NEW
```

**Step 2: Pass campaign_name to save_stills_to_db and add_stills_to_library**

Find and update these calls:

```python
        # Save stills to database and the Reserve
        await save_stills_to_db(stills, campaign_name=campaign_name)
        await add_stills_to_library(stills, user_id, original_filename, campaign_name=campaign_name)
```

**Step 3: Pass campaign_name to save_outputs_to_db**

Find and update this call:

```python
        await save_outputs_to_db(factchecked_drafts, job_id, campaign_name=campaign_name)
```

**Step 4: Update process_job_from_library similarly**

Add `campaign_name = job_data.get("campaign_name")` and pass to `save_outputs_to_db`.

**Step 5: Commit**

```bash
git add app/services/pipeline.py
git commit -m "feat: pass campaign_name through pipeline to storage"
```

---

## Task 5: Make campaign_name required for full pipeline uploads

**Files:**
- Modify: `app/api/upload.py`
- Modify: `frontend/upload.html`

**Step 1: Update upload endpoint validation**

In `upload_content()`, add validation after line 103:

```python
    # Validate campaign_name is required for full pipeline
    if processing_mode != "quick_distill" and not campaign_name:
        raise HTTPException(
            status_code=400,
            detail="Campaign name is required for content generation"
        )
```

**Step 2: Update upload_text endpoint similarly**

Add same validation in `upload_text()` function.

**Step 3: Update upload_url endpoint similarly**

Add same validation in `upload_url()` function.

**Step 4: Update frontend - make campaign field required**

In `frontend/upload.html`, find the campaign-name input (around line 395-402) and update:

```html
<!-- Campaign Name -->
<div>
    <label for="campaign-name" class="form-label form-label-required">Campaign Name</label>
    <input type="text" id="campaign-name" required
        class="input-premium"
        placeholder="e.g., Q1 Webinar Series">
    <p class="form-helper">Required. Group related content under a campaign name.</p>
</div>
```

**Step 5: Add frontend validation in submit handler**

In the form submission JavaScript, add:

```javascript
const campaignName = document.getElementById('campaign-name').value.trim();
if (!campaignName) {
    alert('Campaign name is required');
    return;
}
```

**Step 6: Commit**

```bash
git add app/api/upload.py frontend/upload.html
git commit -m "feat: make campaign_name required for full pipeline"
```

---

## Task 6: Auto-generate campaign_name for Quick Distill

**Files:**
- Modify: `app/api/upload.py`

**Step 1: Add helper function to generate campaign name from filename**

Add at the top of the file after imports:

```python
def generate_campaign_from_filename(filename: str) -> str:
    """Generate a campaign name from filename."""
    from pathlib import Path
    # Remove extension and clean up
    name = Path(filename).stem
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    # Title case
    name = name.title()
    # Limit length
    return name[:200] if len(name) > 200 else name
```

**Step 2: Apply auto-generation for quick_distill mode**

In each upload endpoint, after validation, add:

```python
    # Auto-generate campaign name for Quick Distill if not provided
    if processing_mode == "quick_distill" and not campaign_name:
        campaign_name = generate_campaign_from_filename(file.filename)
```

**Step 3: Commit**

```bash
git add app/api/upload.py
git commit -m "feat: auto-generate campaign name from filename for Quick Distill"
```

---

## Task 7: Add campaign and topic filters to Reserve API

**Files:**
- Modify: `app/api/library.py`

**Step 1: Add new query parameters to get_library**

```python
@router.get("/library")
async def get_library(
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    persona: Optional[str] = Query(None, description="Filter by persona relevance"),
    min_relevance: int = Query(1, description="Minimum relevance score (1-5)"),
    search: Optional[str] = Query(None, description="Search in content", max_length=200),
    campaign: Optional[str] = Query(None, description="Filter by campaign name"),  # NEW
    topic: Optional[str] = Query(None, description="Filter by topic"),  # NEW
    limit: int = Query(50, description="Number of results", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    user_id: int = Depends(get_current_user_id),
):
```

**Step 2: Add campaign filter to query**

```python
        if campaign:
            query += " AND campaign_name = ?"
            params.append(campaign)
```

**Step 3: Add topic filter to query (search in JSON array)**

```python
        if topic:
            # SQLite JSON search - topics_extracted is a JSON array
            query += " AND topics_extracted LIKE ?"
            params.append(f'%"{topic}"%')
```

**Step 4: Add campaign and topics to response entries**

```python
            entries.append({
                "id": row["id"],
                "entry_type": row["entry_type"],
                "content": row["content"],
                "source": row["source"],
                "source_timestamp": row["source_timestamp"],
                "speaker": row["speaker"],
                "date_added": row["date_added"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "topics": json.loads(row["topics_extracted"]) if row.get("topics_extracted") else [],  # NEW
                "campaign_name": row.get("campaign_name"),  # NEW
                "persona_relevance": persona_relevance,
                "times_used": row["times_used"],
                "last_used": row["last_used"],
                "user_notes": row["user_notes"],
            })
```

**Step 5: Add endpoint to get unique campaigns and topics**

```python
@router.get("/library/filters")
async def get_library_filters(user_id: int = Depends(get_current_user_id)):
    """Get unique campaigns and topics for filter dropdowns."""
    async with get_db() as db:
        # Get unique campaign names
        cursor = await db.execute(
            """
            SELECT DISTINCT campaign_name
            FROM content_library
            WHERE user_id = ? AND campaign_name IS NOT NULL
            ORDER BY campaign_name
            """,
            (user_id,)
        )
        campaigns = [row[0] for row in await cursor.fetchall()]

        # Get all topics and count occurrences
        cursor = await db.execute(
            """
            SELECT topics_extracted
            FROM content_library
            WHERE user_id = ? AND topics_extracted IS NOT NULL
            """,
            (user_id,)
        )

        topic_counts = {}
        for row in await cursor.fetchall():
            topics = json.loads(row[0]) if row[0] else []
            for topic in topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Sort topics by frequency
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "campaigns": campaigns,
            "topics": [{"name": t, "count": c} for t, c in sorted_topics[:50]],  # Top 50
        }
```

**Step 6: Commit**

```bash
git add app/api/library.py
git commit -m "feat: add campaign and topic filters to Reserve API"
```

---

## Task 8: Update Reserve UI with campaign and topic filters

**Files:**
- Modify: `frontend/reserve.html`

**Step 1: Add campaign dropdown after persona filter (around line 268)**

```html
<!-- Campaign Filter -->
<div class="flex-1 min-w-[200px]">
    <label for="filter-campaign" class="form-label">Campaign</label>
    <select id="filter-campaign" class="input-premium select-premium">
        <option value="">All Campaigns</option>
    </select>
</div>

<!-- Topic Filter -->
<div class="flex-1 min-w-[200px]">
    <label for="filter-topic" class="form-label">Topic</label>
    <select id="filter-topic" class="input-premium select-premium">
        <option value="">All Topics</option>
    </select>
</div>
```

**Step 2: Add function to load filter options**

In the script section, add:

```javascript
async function loadFilterOptions() {
    try {
        const response = await Auth.fetchWithAuth('/api/library/filters');
        if (!response.ok) throw new Error('Failed to load filters');

        const data = await response.json();

        // Populate campaign dropdown
        const campaignSelect = document.getElementById('filter-campaign');
        campaignSelect.innerHTML = '<option value="">All Campaigns</option>';
        data.campaigns.forEach(campaign => {
            const option = document.createElement('option');
            option.value = campaign;
            option.textContent = campaign;
            campaignSelect.appendChild(option);
        });

        // Populate topic dropdown
        const topicSelect = document.getElementById('filter-topic');
        topicSelect.innerHTML = '<option value="">All Topics</option>';
        data.topics.forEach(item => {
            const option = document.createElement('option');
            option.value = item.name;
            option.textContent = `${item.name} (${item.count})`;
            topicSelect.appendChild(option);
        });
    } catch (err) {
        console.error('Failed to load filter options:', err);
    }
}
```

**Step 3: Call loadFilterOptions on page load**

Add to the initialization:

```javascript
loadFilterOptions();
```

**Step 4: Update loadLibrary to include new filters**

In the `loadLibrary` function, add the new filter parameters:

```javascript
async function loadLibrary() {
    const typeFilter = getActiveTypeFilter();
    const personaFilter = document.getElementById('filter-persona').value;
    const relevanceFilter = document.getElementById('filter-relevance').value;
    const searchFilter = document.getElementById('filter-search').value;
    const campaignFilter = document.getElementById('filter-campaign').value;  // NEW
    const topicFilter = document.getElementById('filter-topic').value;  // NEW

    let url = `/api/library?limit=${pageSize}&offset=${currentPage * pageSize}`;

    if (typeFilter) url += `&entry_type=${encodeURIComponent(typeFilter)}`;
    if (personaFilter) url += `&persona=${encodeURIComponent(personaFilter)}`;
    if (relevanceFilter) url += `&min_relevance=${relevanceFilter}`;
    if (searchFilter) url += `&search=${encodeURIComponent(searchFilter)}`;
    if (campaignFilter) url += `&campaign=${encodeURIComponent(campaignFilter)}`;  // NEW
    if (topicFilter) url += `&topic=${encodeURIComponent(topicFilter)}`;  // NEW
    if (jobIdFilter) url += `&job_id=${encodeURIComponent(jobIdFilter)}`;

    // ... rest of function
}
```

**Step 5: Add event listeners for new filters**

```javascript
document.getElementById('filter-campaign').addEventListener('change', () => {
    currentPage = 0;
    loadLibrary();
});

document.getElementById('filter-topic').addEventListener('change', () => {
    currentPage = 0;
    loadLibrary();
});
```

**Step 6: Update clearAllFilters function**

```javascript
function clearAllFilters() {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    document.querySelector('.filter-chip[data-type=""]').classList.add('active');
    document.getElementById('filter-persona').value = '';
    document.getElementById('filter-relevance').value = '1';
    document.getElementById('filter-search').value = '';
    document.getElementById('filter-campaign').value = '';  // NEW
    document.getElementById('filter-topic').value = '';  // NEW
    currentPage = 0;
    loadLibrary();
}
```

**Step 7: Display campaign and topics on still cards**

Update the card HTML in `renderLibrary`:

```javascript
card.innerHTML = `
    <div class="flex justify-between items-start mb-3">
        <span class="badge text-xs font-semibold uppercase" style="background: ${colors.bg}; color: ${colors.text};">
            ${entry.entry_type}
        </span>
        <div class="flex items-center gap-3">
            ${maxRelevance > 0 ? renderRelevanceDots(maxRelevance) : ''}
            <input type="checkbox" ${isSelected ? 'checked' : ''}
                   class="checkbox-premium" aria-label="Select this still"
                   onclick="event.stopPropagation(); toggleSelect(${entry.id})">
        </div>
    </div>
    ${entry.campaign_name ? `<p class="text-xs text-still-copper mb-2">${escapeHtml(entry.campaign_name)}</p>` : ''}
    <p class="text-still-text text-sm leading-relaxed line-clamp-3 mb-4">${escapeHtml(entry.content)}</p>
    ${entry.topics && entry.topics.length ? `
        <div class="flex flex-wrap gap-1 mb-3">
            ${entry.topics.slice(0, 4).map(topic =>
                `<span class="text-xs px-2 py-0.5 rounded bg-still-copper/10 text-still-copper">${escapeHtml(topic)}</span>`
            ).join('')}
        </div>
    ` : ''}
    ${entry.tags && entry.tags.length ? `
        <div class="flex flex-wrap gap-1 mb-3">
            ${entry.tags.slice(0, 3).map(tag =>
                `<span class="text-xs px-2 py-0.5 rounded" style="background: var(--surface-elevated); color: var(--text-tertiary);">${escapeHtml(tag)}</span>`
            ).join('')}
        </div>
    ` : ''}
    <div class="flex justify-between items-center text-xs text-still-disabled pt-3 border-t" style="border-color: var(--glass-border);">
        <span>Used ${entry.times_used || 0}x</span>
        ${relevanceInfo ? `<span class="text-still-muted">${relevanceInfo}</span>` : ''}
    </div>
`;
```

**Step 8: Commit**

```bash
git add frontend/reserve.html
git commit -m "feat: add campaign and topic filter dropdowns to Reserve UI"
```

---

## Task 9: Test complete flow

**Step 1: Start the server**

Run: `pkill -f uvicorn; cd /path/to/project && uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload`

**Step 2: Test Quick Distill with auto-generated campaign**

1. Go to `/upload.html`
2. Select Quick Distill mode
3. Upload a file WITHOUT entering campaign name
4. Verify campaign is auto-generated from filename
5. Go to Reserve and verify stills have campaign_name and topics

**Step 3: Test Full Pipeline with required campaign**

1. Go to `/upload.html`
2. Keep Full Pipeline mode
3. Try to submit WITHOUT campaign name - should fail
4. Enter campaign name and submit
5. Verify outputs have campaign_name

**Step 4: Test Reserve filters**

1. Go to `/reserve.html`
2. Use campaign dropdown to filter
3. Use topic dropdown to filter
4. Verify stills display campaign and topic badges

**Step 5: Commit final verification**

```bash
git add .
git commit -m "test: verify campaign tagging and topic filters work end-to-end"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `app/database.py` | Add migration for campaign_name, topics columns |
| `app/services/distillation.py` | Extract 2-3 topics per still during distillation |
| `app/services/library_manager.py` | Add campaign_name, topics to validate/save functions |
| `app/services/pipeline.py` | Pass campaign_name through to storage |
| `app/api/upload.py` | Require campaign for full pipeline, auto-gen for Quick Distill |
| `app/api/library.py` | Add campaign/topic filter params, /library/filters endpoint |
| `frontend/upload.html` | Make campaign field required with validation |
| `frontend/reserve.html` | Add campaign/topic dropdowns, display on cards |
