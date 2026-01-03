# Still Lifecycle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand still types from 6 to 10 and add lifecycle management fields for PADR Refresh phase.

**Architecture:** Database-first migration, then backend models, prompts, services, and finally UI. Each layer builds on the previous.

**Tech Stack:** Python/FastAPI, SQLite (local)/PostgreSQL (Supabase), Pydantic, vanilla JS frontend

---

## Task 1: Database Migration - Add Lifecycle Fields

**Files:**
- Modify: `app/database.py`
- Create: Migration via Supabase MCP

**Step 1: Apply Supabase migration for field renames and additions**

Use Supabase MCP to apply migration:

```sql
-- Rename existing fields for consistency
ALTER TABLE stills RENAME COLUMN times_used TO usage_count;
ALTER TABLE stills RENAME COLUMN last_used TO last_used_at;

-- Add lifecycle fields
ALTER TABLE stills ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE stills ADD COLUMN IF NOT EXISTS best_formats TEXT[];
ALTER TABLE stills ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE stills ADD COLUMN IF NOT EXISTS expiration_type TEXT;
ALTER TABLE stills ADD COLUMN IF NOT EXISTS expiration_date DATE;
ALTER TABLE stills ADD COLUMN IF NOT EXISTS performance TEXT DEFAULT 'untested';

-- Add check constraints
ALTER TABLE stills ADD CONSTRAINT stills_status_check
  CHECK (status IS NULL OR status IN ('active', 'evergreen', 'needs_review', 'retired'));
ALTER TABLE stills ADD CONSTRAINT stills_funnel_stage_check
  CHECK (funnel_stage IS NULL OR funnel_stage IN ('awareness', 'consideration', 'decision'));
ALTER TABLE stills ADD CONSTRAINT stills_expiration_type_check
  CHECK (expiration_type IS NULL OR expiration_type IN ('date_bound', 'event_bound', 'evergreen'));
ALTER TABLE stills ADD CONSTRAINT stills_performance_check
  CHECK (performance IS NULL OR performance IN ('high', 'medium', 'low', 'untested'));

-- Create indexes for lifecycle queries
CREATE INDEX IF NOT EXISTS idx_stills_status ON stills(status);
CREATE INDEX IF NOT EXISTS idx_stills_funnel_stage ON stills(funnel_stage);
CREATE INDEX IF NOT EXISTS idx_stills_expiration ON stills(expiration_date) WHERE expiration_date IS NOT NULL;
```

**Step 2: Update local SQLite schema in database.py**

Find the stills table creation in `app/database.py` and update column names and add new columns.

**Step 3: Verify migration**

Run: `pytest tests/test_database.py -v`
Expected: All existing tests pass

**Step 4: Commit**

```bash
git add app/database.py
git commit -m "feat(db): add lifecycle fields to stills table

- Rename times_used -> usage_count, last_used -> last_used_at
- Add status, best_formats, funnel_stage, expiration_type, expiration_date, performance
- Add check constraints and indexes"
```

---

## Task 2: Update StillType Enum and Models

**Files:**
- Modify: `app/models/stills.py`
- Test: `tests/test_services.py`

**Step 1: Write failing test for new still types**

Add to `tests/test_services.py`:

```python
class TestStillTypes:
    """Tests for still type enum."""

    def test_all_still_types_exist(self):
        """Test all 10 still types are defined."""
        from app.models.stills import StillType

        expected_types = [
            'data', 'insight', 'story', 'problem', 'solution', 'quote',
            'framework', 'definition', 'question', 'proof_point'
        ]
        actual_types = [t.value for t in StillType]

        for expected in expected_types:
            assert expected in actual_types, f"Missing still type: {expected}"

        assert len(actual_types) == 10
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_services.py::TestStillTypes::test_all_still_types_exist -v`
Expected: FAIL - only 6 types exist

**Step 3: Update StillType enum**

In `app/models/stills.py`, update the enum:

```python
class StillType(str, Enum):
    """Types of content stills."""
    DATA = "data"
    INSIGHT = "insight"
    STORY = "story"
    PROBLEM = "problem"
    SOLUTION = "solution"
    QUOTE = "quote"
    FRAMEWORK = "framework"
    DEFINITION = "definition"
    QUESTION = "question"
    PROOF_POINT = "proof_point"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_services.py::TestStillTypes::test_all_still_types_exist -v`
Expected: PASS

**Step 5: Add lifecycle enums and update models**

Add new enums and update Pydantic models in `app/models/stills.py`:

```python
class StillStatus(str, Enum):
    """Lifecycle status of a still."""
    ACTIVE = "active"
    EVERGREEN = "evergreen"
    NEEDS_REVIEW = "needs_review"
    RETIRED = "retired"


class FunnelStage(str, Enum):
    """Where in the buyer journey this still fits."""
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    DECISION = "decision"


class ExpirationType(str, Enum):
    """How this still expires."""
    DATE_BOUND = "date_bound"
    EVENT_BOUND = "event_bound"
    EVERGREEN = "evergreen"


class Performance(str, Enum):
    """Performance rating of a still."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTESTED = "untested"


class StillCreate(BaseModel):
    """Model for creating a still from distillation."""
    still_type: StillType
    content: str
    source_location: Optional[str] = None
    source_file: Optional[str] = None
    tags: list[str] = []
    persona_relevance: dict[str, int] = Field(
        default={},
        description="Relevance score (1-5) per persona"
    )
    quote_attribution: Optional[str] = None
    why_relevant: Optional[str] = None
    # New lifecycle fields
    best_formats: list[str] = []
    funnel_stage: Optional[FunnelStage] = None
    expiration_type: Optional[ExpirationType] = None
    expiration_date: Optional[date] = None


class Still(StillCreate):
    """Full still model with database fields."""
    id: str
    job_id: str
    user_id: int
    created_at: datetime
    usage_count: int = 0  # renamed from times_used
    last_used_at: Optional[datetime] = None  # renamed from last_used
    status: StillStatus = StillStatus.ACTIVE
    performance: Performance = Performance.UNTESTED
```

**Step 6: Write test for lifecycle fields**

Add to `tests/test_services.py`:

```python
def test_still_lifecycle_fields(self):
    """Test still model has lifecycle fields."""
    from app.models.stills import Still, StillStatus, FunnelStage, Performance
    from datetime import datetime, date

    still = Still(
        id="test-001",
        job_id="job-001",
        user_id=1,
        still_type="data",
        content="40% improvement",
        created_at=datetime.now(),
        status=StillStatus.ACTIVE,
        funnel_stage=FunnelStage.CONSIDERATION,
        best_formats=["linkedin", "email"],
        expiration_date=date(2025, 12, 31),
        performance=Performance.UNTESTED
    )

    assert still.status == StillStatus.ACTIVE
    assert still.funnel_stage == FunnelStage.CONSIDERATION
    assert "linkedin" in still.best_formats
    assert still.usage_count == 0
```

**Step 7: Run all tests**

Run: `pytest tests/test_services.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add app/models/stills.py tests/test_services.py
git commit -m "feat(models): expand StillType to 10 types, add lifecycle fields

- Add framework, definition, question, proof_point types
- Add StillStatus, FunnelStage, ExpirationType, Performance enums
- Rename times_used -> usage_count, last_used -> last_used_at
- Add best_formats, funnel_stage, expiration_type, expiration_date, performance"
```

---

## Task 3: Update Distillation Prompts

**Files:**
- Modify: `data/prompts/distillation.txt`
- Modify: `data/prompts/distillation_pass2.txt`

**Step 1: Update distillation.txt with all 10 types and new fields**

Replace contents of `data/prompts/distillation.txt`:

```
You are a content strategist distilling source material into reusable stills.

## SOURCE OF TRUTH CONTEXT (anchor your extraction):
Core Narratives: {core_narratives}
Primary Pain Point: {primary_pain_point}
The Promise: {the_promise}

## TARGET PERSONA: {target_persona_title}
Pain points: {persona_pain_points}
Priorities: {persona_priorities}

## SOURCE CONTENT:
{cleaned_transcript}

## TASK: Extract and categorize content stills into these 10 types:

### 1. DATA (statistics, metrics, ROI figures)
- Specific numbers, percentages, time savings, cost reductions
- Example: "40% reduction in turnover"

### 2. INSIGHT (frameworks, methods, actionable tips)
- Processes, best practices, how-to guidance
- Example: "The 3-step recognition framework"

### 3. STORY (customer examples, anecdotes, case studies)
- Real-world examples, before/after scenarios, named examples
- Example: "Sunrise Senior Living reduced turnover from 85% to 52%"

### 4. PROBLEM (challenges, pain points, obstacles)
- Problems the audience faces, industry challenges
- Example: "Teams struggling with staffing shortages"

### 5. SOLUTION (recommendations, strategies, tools)
- Proposed solutions, recommendations, tool suggestions
- Example: "Using ambient monitoring solves manual reporting burden"

### 6. QUOTE (memorable statements with attribution)
- Direct quotes from speakers, testimonials
- Example: "Investing in staff is the profitable thing to do" - Speaker Name

### 7. FRAMEWORK (methodologies, step-by-step processes)
- Named methodologies, numbered approaches, systems
- Example: "The PADR Framework: Pillar, Atomize, Distribute, Refresh"

### 8. DEFINITION (concept explanations, glossary-style)
- Clear definitions of terms, jargon busters
- Example: "Ambient monitoring refers to passive data collection..."

### 9. QUESTION (FAQs, objections, common challenges)
- Questions the audience might ask, objections to address
- Example: "What about HIPAA compliance concerns?"

### 10. PROOF_POINT (third-party validation, citations)
- Research citations, awards, media mentions, certifications
- Example: "As featured in Healthcare Weekly's Top 10 Innovations"

## OUTPUT FORMAT (JSON array):
For each still, include:
{{
  "type": "data|insight|story|problem|solution|quote|framework|definition|question|proof_point",
  "content": "The extracted content, verbatim when possible",
  "source_location": "timestamp or section reference",
  "best_formats": ["linkedin", "blog", "email", "sales", "case_study", "carousel"],
  "funnel_stage": "awareness|consideration|decision",
  "expiration_date": "YYYY-MM-DD or null if evergreen",
  "relevance_to_persona": 1-5,
  "why_relevant": "Brief explanation",
  "tags": ["keyword1", "keyword2"]
}}

## EXTRACTION SCALE (based on content length):
- Short content (<2000 words): Extract 8-15 stills
- Medium content (2000-5000 words): Extract 15-30 stills
- Long content (>5000 words): Extract 30-50 stills

## FIELD GUIDANCE:

**best_formats**: Which output types this still works best for:
- linkedin: Professional insights, data points, frameworks
- blog: Stories, detailed explanations, case studies
- email: Problems, solutions, questions, proof points
- sales: Proof points, data, stories, objections
- case_study: Stories, data, before/after
- carousel: Frameworks, step-by-step, definitions

**funnel_stage**:
- awareness: Introduces problems, defines concepts, raises questions
- consideration: Compares solutions, provides frameworks, shares stories
- decision: Proof points, ROI data, objection handling

**expiration_date**:
- Set for time-bound statistics (e.g., "2024 data" expires end of 2025)
- Set null for evergreen content (frameworks, definitions, timeless insights)

## PRIORITIZATION:
Rank each still's relevance to {target_persona_title} on 1-5 scale:
- 5 = Directly addresses their top pain point or priority
- 4 = Highly relevant to their role
- 3 = Generally useful
- 2 = Marginally relevant
- 1 = Not specifically relevant but good content

## EXTRACTION RULES:
- Extract VERBATIM quotes when possible (preserve exact wording)
- Include enough context for the still to stand alone
- Don't over-summarize - keep the richness of the original
- For QUOTE type, always include speaker attribution if known
- For DATA type, always check if an expiration_date applies
```

**Step 2: Update distillation_pass2.txt with all 10 types**

Replace contents of `data/prompts/distillation_pass2.txt`:

```
You are a content strategist performing a SECOND PASS extraction to find overlooked content stills.

## SOURCE OF TRUTH CONTEXT:
Core Narratives: {core_narratives}
Primary Pain Point: {primary_pain_point}
The Promise: {the_promise}

## TARGET PERSONA: {target_persona_title}
Pain points: {persona_pain_points}
Priorities: {persona_priorities}

## FIRST PASS ALREADY EXTRACTED ({first_pass_count} stills):
{first_pass_stills}

## SOURCE CONTENT (review again for missed content):
{cleaned_transcript}

## TASK: Find content stills that were MISSED in the first pass.

## WHAT TO LOOK FOR:

### Overlooked Types (especially these often-missed categories):

1. **FRAMEWORK** - Named methodologies buried in explanations
2. **DEFINITION** - Terms explained in passing but valuable as standalone
3. **QUESTION** - Objections or FAQs mentioned briefly
4. **PROOF_POINT** - Third-party mentions, research citations, awards

### Also check for missed:

5. **QUOTE** - Direct quotes from speakers not yet captured
6. **DATA** - Statistics mentioned in passing
7. **STORY** - Brief anecdotes glossed over
8. **PROBLEM** - Secondary issues mentioned
9. **SOLUTION** - Quick recommendations or tips
10. **INSIGHT** - Wisdom buried in transitions or asides

## OUTPUT FORMAT (same as first pass):
{{
  "type": "data|insight|story|problem|solution|quote|framework|definition|question|proof_point",
  "content": "The extracted content",
  "source_location": "timestamp or section",
  "best_formats": ["linkedin", "blog", "email", "sales", "case_study", "carousel"],
  "funnel_stage": "awareness|consideration|decision",
  "expiration_date": "YYYY-MM-DD or null",
  "relevance_to_persona": 1-5,
  "why_relevant": "Brief explanation",
  "tags": ["keyword1", "keyword2"]
}}

## RULES:
- ONLY extract content NOT already in the first pass list above
- Do NOT rephrase or duplicate existing stills
- Quality over quantity - only genuinely new valuable content
- Include source_location to prove it's different content
- Aim for 3-10 additional stills depending on content richness
```

**Step 3: Commit**

```bash
git add data/prompts/distillation.txt data/prompts/distillation_pass2.txt
git commit -m "feat(prompts): expand distillation to 10 types with lifecycle fields

- Add framework, definition, question, proof_point extraction
- Include Source of Truth context for guided extraction
- Add best_formats, funnel_stage, expiration_date per still
- Scale extraction targets by content length"
```

---

## Task 4: Update Distillation Service

**Files:**
- Modify: `app/services/distillation.py`
- Modify: `app/services/library_manager.py`

**Step 1: Read current distillation.py to understand structure**

Identify where stills are parsed and stored.

**Step 2: Update distill_content() to pass Source of Truth context**

Find the function that renders the distillation prompt and add new template variables:
- `core_narratives`
- `primary_pain_point`
- `the_promise`

**Step 3: Update still parsing to handle new fields**

Where stills are parsed from LLM response, extract:
- `best_formats` (default to empty list)
- `funnel_stage` (default to None)
- `expiration_date` (parse as date or None)

**Step 4: Update library_manager.py validation**

Update `validate_still()` to accept new still types and fields.

**Step 5: Update group_stills_by_type()**

Ensure the grouping function includes all 10 types.

**Step 6: Write test for new type grouping**

Add to `tests/test_services.py`:

```python
def test_group_stills_includes_new_types(self):
    """Test grouping includes all 10 still types."""
    from app.services.distillation import group_stills_by_type

    stills = [
        {"still_type": "framework", "content": "3-step process"},
        {"still_type": "definition", "content": "Term means..."},
        {"still_type": "question", "content": "What about X?"},
        {"still_type": "proof_point", "content": "As featured in..."},
    ]

    grouped = group_stills_by_type(stills)

    assert "framework" in grouped
    assert "definition" in grouped
    assert "question" in grouped
    assert "proof_point" in grouped
    assert len(grouped["framework"]) == 1
```

**Step 7: Run tests**

Run: `pytest tests/test_services.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add app/services/distillation.py app/services/library_manager.py tests/test_services.py
git commit -m "feat(distillation): support 10 still types and lifecycle fields

- Pass Source of Truth context to prompts
- Parse best_formats, funnel_stage, expiration_date
- Update validation for new types
- Extend group_stills_by_type for all 10 types"
```

---

## Task 5: Create Lifecycle Service

**Files:**
- Create: `app/services/lifecycle.py`
- Test: `tests/test_services.py`

**Step 1: Write failing test for lifecycle service**

Add to `tests/test_services.py`:

```python
class TestLifecycleService:
    """Tests for lifecycle management."""

    @pytest.mark.asyncio
    async def test_check_expiring_stills_function_exists(self):
        """Test lifecycle functions exist."""
        from app.services.lifecycle import check_expiring_stills, get_lifecycle_summary

        assert callable(check_expiring_stills)
        assert callable(get_lifecycle_summary)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_services.py::TestLifecycleService -v`
Expected: FAIL - module not found

**Step 3: Create lifecycle.py**

Create `app/services/lifecycle.py`:

```python
"""Lifecycle management for stills - handles expiration and status updates."""
from datetime import date, timedelta
from typing import Optional
import aiosqlite

from app.database import get_db_path


async def check_expiring_stills(days_threshold: int = 30) -> int:
    """
    Mark stills as 'needs_review' when expiration is approaching.

    Args:
        days_threshold: Days before expiration to flag (default 30)

    Returns:
        Count of stills flagged
    """
    threshold_date = date.today() + timedelta(days=days_threshold)

    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute("""
            UPDATE stills
            SET status = 'needs_review'
            WHERE status = 'active'
              AND expiration_date IS NOT NULL
              AND expiration_date <= ?
            RETURNING id
        """, (threshold_date.isoformat(),))

        results = await cursor.fetchall()
        await db.commit()

        return len(results)


async def get_lifecycle_summary(user_id: int) -> dict:
    """
    Get counts by status for dashboard/UI.

    Args:
        user_id: User to get summary for

    Returns:
        Dict with counts per status and expiring_soon count
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'active' OR status IS NULL) as active,
                COUNT(*) FILTER (WHERE status = 'evergreen') as evergreen,
                COUNT(*) FILTER (WHERE status = 'needs_review') as needs_review,
                COUNT(*) FILTER (WHERE status = 'retired') as retired,
                COUNT(*) FILTER (WHERE expiration_date <= date('now', '+7 days')) as expiring_soon
            FROM stills
            WHERE user_id = ?
        """, (user_id,))

        row = await cursor.fetchone()

        return {
            "active": row["active"] or 0,
            "evergreen": row["evergreen"] or 0,
            "needs_review": row["needs_review"] or 0,
            "retired": row["retired"] or 0,
            "expiring_soon": row["expiring_soon"] or 0,
        }


async def update_still_status(still_id: str, new_status: str) -> bool:
    """
    Update the status of a still.

    Args:
        still_id: ID of still to update
        new_status: New status value

    Returns:
        True if updated, False if not found
    """
    valid_statuses = ['active', 'evergreen', 'needs_review', 'retired']
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}")

    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute("""
            UPDATE stills SET status = ? WHERE id = ?
        """, (new_status, still_id))

        await db.commit()
        return cursor.rowcount > 0
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_services.py::TestLifecycleService -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/lifecycle.py tests/test_services.py
git commit -m "feat(lifecycle): add lifecycle management service

- check_expiring_stills() flags approaching expirations
- get_lifecycle_summary() returns status counts for UI
- update_still_status() for manual status changes"
```

---

## Task 6: Add Usage Tracking to Drafting Service

**Files:**
- Modify: `app/services/drafting.py`

**Step 1: Read current drafting.py to find output creation**

Identify where outputs are created and stills are selected.

**Step 2: Add record_still_usage function**

Add to `app/services/drafting.py`:

```python
async def record_still_usage(still_ids: list[str], output_id: int) -> None:
    """
    Increment usage counts and update timestamps for stills used in output.

    Args:
        still_ids: List of still IDs that were used
        output_id: ID of the output they were used in
    """
    if not still_ids:
        return

    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(get_db_path()) as db:
        # Update each still's usage count and timestamp
        placeholders = ','.join('?' * len(still_ids))
        await db.execute(f"""
            UPDATE stills
            SET usage_count = COALESCE(usage_count, 0) + 1,
                last_used_at = ?
            WHERE id IN ({placeholders})
        """, [now] + still_ids)

        # Update atoms_used on output
        import json
        await db.execute("""
            UPDATE outputs
            SET atoms_used = ?
            WHERE id = ?
        """, (json.dumps(still_ids), output_id))

        await db.commit()
```

**Step 3: Wire up usage tracking in output creation**

Find where outputs are created and add call to `record_still_usage()`.

**Step 4: Commit**

```bash
git add app/services/drafting.py
git commit -m "feat(drafting): track still usage when generating content

- Add record_still_usage() to increment counts
- Update last_used_at timestamp
- Store still IDs in atoms_used on output"
```

---

## Task 7: Add Admin Lifecycle Endpoint

**Files:**
- Modify: `app/api/admin.py`

**Step 1: Add lifecycle check endpoint**

Add to `app/api/admin.py`:

```python
from app.services.lifecycle import check_expiring_stills, get_lifecycle_summary

@router.post("/lifecycle/check-expirations")
async def trigger_expiration_check(days: int = 30):
    """
    Trigger check for expiring stills and flag them as needs_review.

    This can be run manually or via cron job.
    """
    count = await check_expiring_stills(days)
    return {"stills_flagged": count, "threshold_days": days}


@router.get("/lifecycle/summary/{user_id}")
async def get_user_lifecycle_summary(user_id: int):
    """Get lifecycle status counts for a user."""
    summary = await get_lifecycle_summary(user_id)
    return summary
```

**Step 2: Commit**

```bash
git add app/api/admin.py
git commit -m "feat(api): add lifecycle admin endpoints

- POST /admin/lifecycle/check-expirations - flag expiring stills
- GET /admin/lifecycle/summary/{user_id} - get status counts"
```

---

## Task 8: Update Reserve UI - Type Colors

**Files:**
- Modify: `frontend/reserve.html`

**Step 1: Add new type colors**

Find `typeColors` object (around line 665) and add:

```javascript
const typeColors = {
    'data': { bg: 'rgba(96, 165, 250, 0.15)', text: '#60A5FA' },
    'story': { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
    'insight': { bg: 'rgba(192, 132, 252, 0.15)', text: '#C084FC' },
    'problem': { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
    'solution': { bg: 'rgba(233, 168, 114, 0.15)', text: '#E9A872' },
    'quote': { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
    // New types
    'framework': { bg: 'rgba(45, 212, 191, 0.15)', text: '#2DD4BF' },
    'definition': { bg: 'rgba(148, 163, 184, 0.15)', text: '#94A3B8' },
    'question': { bg: 'rgba(244, 114, 182, 0.15)', text: '#F472B6' },
    'proof_point': { bg: 'rgba(34, 197, 94, 0.15)', text: '#22C55E' }
};
```

**Step 2: Add CSS variables for new types**

Find the CSS section with `.still-card[data-type="..."]` rules and add:

```css
.still-card[data-type="framework"] { --type-color: #2DD4BF; }
.still-card[data-type="definition"] { --type-color: #94A3B8; }
.still-card[data-type="question"] { --type-color: #F472B6; }
.still-card[data-type="proof_point"] { --type-color: #22C55E; }
```

**Step 3: Commit**

```bash
git add frontend/reserve.html
git commit -m "feat(ui): add colors for 4 new still types

- framework (teal), definition (slate), question (pink), proof_point (emerald)"
```

---

## Task 9: Update Reserve UI - Filters

**Files:**
- Modify: `frontend/reserve.html`

**Step 1: Add status filter dropdown**

Find the filter section and add status filter:

```html
<select id="filter-status" class="filter-select">
    <option value="">All Statuses</option>
    <option value="active">Active</option>
    <option value="evergreen">Evergreen</option>
    <option value="needs_review">Needs Review</option>
    <option value="retired">Retired</option>
</select>
```

**Step 2: Add funnel stage filter**

```html
<select id="filter-funnel" class="filter-select">
    <option value="">All Funnel Stages</option>
    <option value="awareness">Awareness</option>
    <option value="consideration">Consideration</option>
    <option value="decision">Decision</option>
</select>
```

**Step 3: Add sort options**

```html
<select id="sort-by" class="filter-select">
    <option value="newest">Newest First</option>
    <option value="oldest">Oldest First</option>
    <option value="most_used">Most Used</option>
    <option value="never_used">Never Used</option>
    <option value="expiring_soon">Expiring Soon</option>
</select>
```

**Step 4: Update type filter chips to include new types**

Find the type filter chips section and add:
- framework
- definition
- question
- proof_point

**Step 5: Wire up filter logic in JavaScript**

Update the `filterLibrary()` function to handle new filters.

**Step 6: Commit**

```bash
git add frontend/reserve.html
git commit -m "feat(ui): add status, funnel stage, and sort filters to Reserve

- Filter by status (active/evergreen/needs_review/retired)
- Filter by funnel stage (awareness/consideration/decision)
- Sort by usage count and expiration"
```

---

## Task 10: Update Reserve UI - Card Display

**Files:**
- Modify: `frontend/reserve.html`

**Step 1: Update card template to show lifecycle data**

Find the card rendering function and add:

```javascript
// Add status badge if not active
if (entry.status && entry.status !== 'active') {
    const statusBadge = document.createElement('span');
    statusBadge.className = `status-badge status-${entry.status}`;
    statusBadge.textContent = entry.status.replace('_', ' ');
    card.appendChild(statusBadge);
}

// Add funnel stage badge
if (entry.funnel_stage) {
    const funnelBadge = document.createElement('span');
    funnelBadge.className = 'funnel-badge';
    funnelBadge.textContent = entry.funnel_stage;
    card.appendChild(funnelBadge);
}

// Add expiration warning for data stills
if (entry.expiration_date) {
    const expDate = new Date(entry.expiration_date);
    const daysUntil = Math.ceil((expDate - new Date()) / (1000 * 60 * 60 * 24));

    if (daysUntil <= 30) {
        const warning = document.createElement('span');
        warning.className = daysUntil <= 7 ? 'expiration-critical' : 'expiration-warning';
        warning.textContent = `Expires: ${daysUntil}d`;
        card.appendChild(warning);
    }
}

// Add usage stats
const usageStats = document.createElement('div');
usageStats.className = 'usage-stats';
usageStats.innerHTML = `
    <span>Used ${entry.usage_count || 0} times</span>
    ${entry.last_used_at ? `<span>Last: ${formatDate(entry.last_used_at)}</span>` : ''}
`;
card.appendChild(usageStats);
```

**Step 2: Add CSS for new badges and warnings**

```css
.status-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
}
.status-needs_review {
    background: rgba(251, 191, 36, 0.2);
    color: #FBBF24;
    border: 1px solid rgba(251, 191, 36, 0.4);
}
.status-retired {
    background: rgba(100, 100, 100, 0.2);
    color: #888;
    text-decoration: line-through;
}
.status-evergreen {
    background: rgba(34, 197, 94, 0.2);
    color: #22C55E;
}
.funnel-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    background: rgba(255,255,255,0.1);
    color: #999;
}
.expiration-warning {
    color: #FBBF24;
    font-size: 0.75rem;
}
.expiration-critical {
    color: #F87171;
    font-size: 0.75rem;
    font-weight: 600;
}
.usage-stats {
    display: flex;
    gap: 12px;
    font-size: 0.75rem;
    color: #666;
    margin-top: 8px;
}
```

**Step 3: Commit**

```bash
git add frontend/reserve.html
git commit -m "feat(ui): show lifecycle data on still cards

- Status badges (needs_review, retired, evergreen)
- Funnel stage badges
- Expiration warnings (amber <30d, red <7d)
- Usage count and last used date"
```

---

## Task 11: Update Reserve API to Return Lifecycle Fields

**Files:**
- Modify: `app/api/library.py` (or wherever Reserve API is)

**Step 1: Update query to include new fields**

Find the endpoint that returns stills for Reserve and update SELECT to include:
- status
- best_formats
- funnel_stage
- expiration_type
- expiration_date
- usage_count
- last_used_at
- performance

**Step 2: Add sorting parameter**

Add `sort_by` query parameter to support:
- newest (created_at DESC)
- oldest (created_at ASC)
- most_used (usage_count DESC)
- never_used (usage_count = 0)
- expiring_soon (expiration_date ASC WHERE NOT NULL)

**Step 3: Add filter parameters**

Add query parameters:
- status (filter by status)
- funnel_stage (filter by funnel stage)

**Step 4: Commit**

```bash
git add app/api/library.py
git commit -m "feat(api): return lifecycle fields and support new filters

- Include all lifecycle fields in response
- Add sort_by parameter (most_used, never_used, expiring_soon)
- Add status and funnel_stage filter parameters"
```

---

## Task 12: Integration Test

**Files:**
- Modify: `tests/test_e2e.py`

**Step 1: Write integration test for full lifecycle**

```python
@pytest.mark.asyncio
async def test_still_lifecycle_flow(auth_client):
    """Test full lifecycle: create still -> use in content -> check expiration."""
    # 1. Create a job with stills that have lifecycle fields
    # 2. Verify stills are returned with lifecycle data
    # 3. Generate content using stills
    # 4. Verify usage_count incremented
    # 5. Trigger expiration check
    # 6. Verify status updated
    pass  # Implement based on actual API structure
```

**Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 3: Final commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add integration test for still lifecycle flow"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Database migration | database.py, Supabase |
| 2 | Update StillType enum + models | models/stills.py |
| 3 | Update distillation prompts | prompts/*.txt |
| 4 | Update distillation service | services/distillation.py |
| 5 | Create lifecycle service | services/lifecycle.py |
| 6 | Add usage tracking | services/drafting.py |
| 7 | Add admin endpoints | api/admin.py |
| 8 | UI: type colors | frontend/reserve.html |
| 9 | UI: filters | frontend/reserve.html |
| 10 | UI: card display | frontend/reserve.html |
| 11 | API: lifecycle fields | api/library.py |
| 12 | Integration test | tests/test_e2e.py |

**Estimated commits:** 12
**Estimated time:** 2-3 hours of focused implementation
