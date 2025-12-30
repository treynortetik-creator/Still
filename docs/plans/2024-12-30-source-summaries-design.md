# Source Summaries for Cross-Source Content Generation

## Problem

When generating content from stills across multiple sources, the AI lacks context about where each piece of content originated. A stat like "47% reduction in turnover" could be from a healthcare webinar or a tech case study - the AI can't tell, leading to awkward tone mixing or misattribution.

## Solution

Generate and store a summary of each source during the pipeline. When drafting content from multiple sources, inject these summaries as context right before the stills content.

---

## Implementation

### 1. Database Schema

Add column to `jobs` table:

```sql
ALTER TABLE jobs ADD COLUMN source_summary TEXT;
```

Update in `app/database.py` jobs table definition.

---

### 2. Summarization Service

**New file:** `app/services/summarization.py`

```python
async def generate_source_summary(
    cleaned_transcript: str,
    job_id: str,
    user_id: int = None
) -> Tuple[str, float]:
    """
    Generate a summary of source content.

    Returns:
        (summary_text, cost_in_dollars)
    """
```

- Uses `call_llm_text()` with `step="summarization"`
- Truncates transcript to ~50k chars (plenty for summary)
- Returns empty string on failure (non-fatal)
- Tracks cost for billing

**Prompt focus:**
- Main topic/theme
- Key speakers/sources
- Primary statistics
- Core problems discussed
- Solutions/recommendations
- Overall tone

---

### 3. Pipeline Integration

**File:** `app/services/pipeline.py`

After transcription completes, run summarization in parallel with distillation:

```python
# After transcript is ready
summary_task = asyncio.create_task(
    generate_source_summary(cleaned_transcript, job_id, user_id)
)

# Distillation pass 1
stills, distill_cost = await distill_content(...)

# Await summary (should be done by now, ran in parallel)
try:
    source_summary, summary_cost = await summary_task
    # Save to jobs table
    await update_job_summary(job_id, source_summary)
    total_cost += summary_cost
except Exception as e:
    logger.error(f"Job {job_id}: Summary failed (non-fatal): {e}")
```

**Key points:**
- Runs parallel with distillation - no added latency
- Non-blocking on failure
- Cost tracked and added to job total

---

### 4. Drafting Integration

**File:** `app/services/drafting.py`

Modify drafting functions (`draft_linkedin_posts`, `draft_blog_post`, `draft_email`, etc.):

1. Extract unique `job_id`s from input stills
2. If multiple sources, fetch summaries from `jobs` table
3. Build source context block
4. Inject into prompt right before the stills content

```python
def build_source_context(stills: list[dict], summaries: dict[str, dict]) -> str:
    """
    Build source context block for multi-source generation.

    Args:
        stills: List of still dicts with job_id
        summaries: Dict mapping job_id -> {campaign_name, summary}

    Returns:
        Context string, or empty if single source
    """
    job_ids = list(set(s.get("job_id") for s in stills if s.get("job_id")))

    if len(job_ids) <= 1:
        return ""  # Single source, no context needed

    context = "SOURCE CONTEXT:\n---\n"
    for job_id in job_ids:
        info = summaries.get(job_id, {})
        campaign = info.get("campaign_name", "Unknown Source")
        summary = info.get("summary", "")

        source_stills = [s for s in stills if s.get("job_id") == job_id]

        context += f'\nSource: "{campaign}"\n'
        if summary:
            context += f"Summary: {summary}\n"
        context += f"({len(source_stills)} pieces selected from this source)\n"

    context += "---\n\n"
    return context
```

**Injection point:** Right before the formatted stills in the prompt.

---

### 5. Admin Panel Updates

**A. Settings Page (`app/templates/admin/settings.html`)**

Add "Summarization" dropdown in model selection section, following existing pattern:

```html
<div class="model-step">
    <label for="summarization-model">Summarization</label>
    <select id="summarization-model" name="summarization">
        <!-- Populated by loadOpenRouterModels() -->
    </select>
    <button onclick="loadOpenRouterModels('summarization')">Load Models</button>
</div>
```

**B. Settings Manager (`app/services/settings_manager.py`)**

Add to `DEFAULT_MODELS`:
```python
"summarization": "google/gemini-2.0-flash-lite"
```

Update `init_default_settings()` to include summarization.

**C. Prompt Template**

Add `summarization` prompt to `prompt_templates` table in init:
- Template name: `summarization`
- Default model: `google/gemini-2.0-flash-lite` (cheap, fast)
- Max tokens: 500

This will automatically appear in the prompt editor UI.

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/database.py` | Add `source_summary` column to jobs table |
| `app/services/summarization.py` | **New file** - summarization service |
| `app/services/pipeline.py` | Run summarization parallel with distillation |
| `app/services/drafting.py` | Add `build_source_context()`, modify drafting functions |
| `app/services/settings_manager.py` | Add summarization to defaults |
| `app/templates/admin/settings.html` | Add summarization model dropdown |
| `data/prompts/summarization.txt` | **New file** - summary prompt template |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Summary generation fails | Log error, continue pipeline, leave `source_summary` NULL |
| Summary is NULL when drafting | Skip that source's summary in context block |
| Single-source generation | Don't add source context (unnecessary) |
| Transcript too short (<100 chars) | Skip summarization, return empty string |

---

## Testing

1. Upload content, verify `source_summary` populated in jobs table
2. Upload second content from different campaign
3. Select stills from both in Reserve
4. Generate content - verify source context appears in prompt (check logs)
5. Generate from single source - verify no source context added
6. Test with failed summary (mock error) - verify pipeline completes
7. Verify admin panel shows summarization model dropdown
8. Verify summarization prompt appears in prompt editor
