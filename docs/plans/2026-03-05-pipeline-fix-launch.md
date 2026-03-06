# Pipeline Fix & Launch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 16 pipeline issues (2 critical, 4 high, 6 medium, 6 low) to make Still fully operational for Brette Digon demo by March 26, 2026.

**Architecture:** FastAPI + vanilla JS frontend, dual SQLite/PostgreSQL support via db_utils helpers. All AI calls go through OpenRouter. Prompt templates stored in `data/prompts/*.txt` and synced to `prompt_templates` DB table on startup.

**Tech Stack:** Python/FastAPI, asyncpg/aiosqlite, OpenRouter API, Jinja-style `{var}` templates

---

## Task 1: C1 — Fix Variable Name Mismatch (atoms → stills) in Templates + prompt_manager.py

**Files:**
- Modify: `data/prompts/linkedin_draft.txt:18-19`
- Modify: `data/prompts/blog_draft.txt:18-23`
- Modify: `data/prompts/email_draft.txt:17`
- Modify: `app/services/prompt_manager.py:53-72`

**What to do:**

1. In `data/prompts/linkedin_draft.txt` line 19: Change `{selected_atoms_for_linkedin}` → `{selected_stills_for_linkedin}`

2. In `data/prompts/blog_draft.txt` lines 19-23: Change all atom references to stills:
   - `{problem_atoms}` → `{problem_stills}`
   - `{insight_atoms}` → `{insight_stills}`
   - `{solution_atoms}` → `{solution_stills}`
   - `{data_atoms}` → `{data_stills}`
   - `{story_atoms}` → `{story_stills}`
   Also update the label on line 18 from "ATOMS TO USE:" to "STILLS TO USE:"

3. In `data/prompts/email_draft.txt` line 17: Change `{selected_atoms}` → `{selected_stills}`
   Also update label on line 16 from "ATOMS TO USE:" to "STILLS TO USE:"

4. In `app/services/prompt_manager.py`, update the `default_prompts` variable lists:
   - `linkedin_draft` variables (line 54): Change `"selected_atoms_for_linkedin"` → `"selected_stills_for_linkedin"`
   - `blog_draft` variables (line 62): Change `"problem_atoms"` → `"problem_stills"`, `"insight_atoms"` → `"insight_stills"`, `"solution_atoms"` → `"solution_stills"`, `"data_atoms"` → `"data_stills"`, `"story_atoms"` → `"story_stills"`
   - `email_draft` variables (line 70): Change `"selected_atoms"` → `"selected_stills"`

5. Also update the linkedin_draft.txt references on lines 48-51 from "atoms" to "stills" in the variation instructions.

**NOTE:** The Python code in `drafting.py` already uses `_stills` variable names (see lines 257, 362-367, 448). The templates are out of sync with the code. This fix makes them match.

**Verify:** `grep -r "atoms" data/prompts/` should return zero matches after fix. `grep -r "atoms" app/services/prompt_manager.py` should also return zero.

---

## Task 2: C2 — Remove Duplicate Output Format from Distillation Prompts

**Files:**
- Modify: `data/prompts/distillation.txt:57-101`
- Modify: `data/prompts/distillation_pass2.txt:38-49`

**What to do:**

1. In `data/prompts/distillation.txt`: Remove the `## OUTPUT FORMAT (JSON array):` section (lines 57-68) and the `## EXTRACTION SCALE`, `## FIELD GUIDANCE`, and `## EXTRACTION RULES` sections (lines 71-109). The Python code in `distillation.py` lines 119-168 already appends a complete `OUTPUT FORMAT` block with the correct `"stills"` key, topic extraction, and quote instructions. Keep lines 1-56 (the task description, still type definitions) and line 96 (prioritization section, renumber if needed).

   Actually, more precisely: Keep lines 1-55 (types 1-10 definitions) and the `## PRIORITIZATION` section (lines 95-101). Remove lines 57-68 (OUTPUT FORMAT), 71-93 (EXTRACTION SCALE, FIELD GUIDANCE), and 103-109 (EXTRACTION RULES). The code-appended block in `distillation.py` covers all of this.

2. In `data/prompts/distillation_pass2.txt`: Remove the `## OUTPUT FORMAT` section (lines 38-49). The Python code in `distillation.py` lines 334-369 appends a complete output format block for pass 2.

3. In `distillation.py` line 193: Simplify `result.get("stills", result.get("atoms", []))` to `result.get("stills", [])` since we've now standardized the format instruction.

**Verify:** Each distillation prompt file should have zero `OUTPUT FORMAT` sections. The code-appended blocks remain the single source of truth.

---

## Task 3: M1 — Update Deprecated Model Default in still_matcher.py

**Files:**
- Modify: `app/services/still_matcher.py:73`

**What to do:**

1. Change line 73:
   ```python
   model = await get_global_setting('still_matching_model', 'google/gemini-flash-1.5')
   ```
   To:
   ```python
   model = await get_global_setting('still_matching_model', 'google/gemini-2.5-flash')
   ```

**Verify:** `grep "gemini-flash-1.5" app/services/still_matcher.py` returns zero matches.

---

## Task 4: H1 — Fix Sommelier to Search stills Table (UNION with content_library)

**Files:**
- Modify: `app/services/sommelier.py`

**What to do:**

The entire `search_stills()` function needs to be updated. Currently it only queries `content_library`. Fix it to search both `stills` and `content_library` using UNION, with a `source_table` tag.

1. Replace the empty-check query (lines 187-195) to check BOTH tables:
   ```python
   stills_count = await fetchone(
       db,
       "SELECT COUNT(*) as count FROM stills WHERE user_id = ?",
       (user_id,)
   )
   reserve_count = await fetchone(
       db,
       "SELECT COUNT(*) as count FROM content_library WHERE user_id = ?",
       (user_id,)
   )
   total = (stills_count["count"] if stills_count else 0) + (reserve_count["count"] if reserve_count else 0)
   if total == 0:
       return [], "Your library is empty. Process some content first!", total_cost
   ```

2. Replace the search query (lines 200-226) with a UNION query that searches both tables. The `stills` table has columns: `id, still_type, content, tags, ...` while `content_library` has: `id, entry_type, content, tags, ...`. Build a UNION:

   ```python
   # Build keyword conditions for stills table
   stills_conditions = []
   stills_params = [user_id]
   for keyword in search_keywords[:10]:
       stills_conditions.append("(content ILIKE ? OR tags::text ILIKE ?)" if settings.use_postgres else "(content LIKE ? OR tags LIKE ?)")
       stills_params.extend([f"%{keyword}%", f"%{keyword}%"])

   stills_where = " OR ".join(stills_conditions) if stills_conditions else "1=1"

   # Build keyword conditions for content_library table
   cl_conditions = []
   cl_params = [user_id]
   for keyword in search_keywords[:10]:
       cl_conditions.append("(content ILIKE ? OR tags::text ILIKE ?)" if settings.use_postgres else "(content LIKE ? OR tags LIKE ?)")
       cl_params.extend([f"%{keyword}%", f"%{keyword}%"])

   cl_where = " OR ".join(cl_conditions) if cl_conditions else "1=1"

   query = f"""
       SELECT id, still_type as entry_type, content, campaign_name as source, tags, 'stills' as source_table
       FROM stills
       WHERE user_id = ? AND ({stills_where})
       UNION ALL
       SELECT id, entry_type, content, source, tags, 'reserve' as source_table
       FROM content_library
       WHERE user_id = ? AND ({cl_where})
       LIMIT 50
   """
   all_params = tuple(stills_params + cl_params)
   rows = await fetchall(db, query, all_params)
   ```

3. Update the result formatting (lines 234-242) to include `source_table`:
   ```python
   stills_for_ranking.append({
       "id": row["id"],
       "type": row["entry_type"],
       "content": row["content"][:500],
       "source": row["source"],
       "tags": json.loads(row["tags"]) if row["tags"] else [],
       "source_table": row["source_table"],
   })
   ```

4. Update the final results building (lines 293-318) to fetch from the correct table based on `source_table`:
   ```python
   for still in stills_for_ranking:
       if still["id"] in ranked_ids:
           ranking = ranked_ids[still["id"]]

           # Fetch from correct table
           if still.get("source_table") == "stills":
               row = await fetchone(db, "SELECT id, still_type as entry_type, content, campaign_name as source, NULL as source_timestamp, tags, NULL as persona_relevance, usage_count as times_used FROM stills WHERE id = ?", (still["id"],))
           else:
               row = await fetchone(db, "SELECT * FROM content_library WHERE id = ?", (still["id"],))

           if row:
               results.append({
                   "id": row["id"],
                   "entry_type": row["entry_type"] if "entry_type" in row.keys() else row.get("still_type", "insight"),
                   "content": row["content"],
                   "source": row["source"] if "source" in row.keys() else row.get("campaign_name", ""),
                   "source_timestamp": row.get("source_timestamp"),
                   "tags": json.loads(row["tags"]) if row["tags"] else [],
                   "persona_relevance": json.loads(row["persona_relevance"]) if row.get("persona_relevance") else {},
                   "times_used": row.get("times_used", 0),
                   "relevance_score": ranking.get("relevance_score", 3),
                   "why_relevant": ranking.get("why_relevant", "Matched search criteria"),
                   "source_table": still.get("source_table", "stills"),
               })
   ```

5. Update the empty result message (line 195) to say "Your library is empty" instead of "Your Reserve is empty".

**Verify:** Sommelier queries should return results from both `stills` and `content_library` tables. Results should include `source_table` field.

---

## Task 5: H2 — SOT Approval Gate Already Exists

**Files:**
- Review: `app/services/pipeline.py:303-329`

**What to do:**

Looking at the code, the SOT approval gate ALREADY EXISTS in `pipeline.py` lines 318-329. When `auto_approve` is False, the pipeline pauses at `AWAITING_APPROVAL` status and returns. The `resume_pipeline_from_distillation()` function (line 500) handles continuation after approval.

**This issue is already implemented.** No code changes needed. Mark as resolved.

The `approve_source_of_truth()` function in `source_of_truth.py` correctly sets `is_approved = True` and `approved_at`. The only missing piece noted in the PRD is that `approve_source_of_truth` doesn't trigger pipeline continuation — but that's handled by the API endpoint calling `resume_pipeline_from_distillation()` after approval.

**Verify:** Confirm the API endpoint for SOT approval calls `resume_pipeline_from_distillation`.

---

## Task 6: H3 — Add Brand Voice and SOT Context to Editing Step

**Files:**
- Modify: `app/services/editing.py`
- Modify: `data/prompts/audience_edit.txt`

**What to do:**

1. In `app/services/editing.py`, add brand voice and SOT imports at the top (after line 8):
   ```python
   from app.services.brand_voice_analyzer import get_brand_voice_template_vars
   from app.services.source_of_truth import get_source_of_truth_template_vars
   ```

2. In the `edit_for_audience()` function, after the variables dict is built (after line 44), inject brand voice and SOT:
   ```python
   # Inject brand voice variables if user_id provided
   if user_id:
       brand_vars = await get_brand_voice_template_vars(user_id, content_type=content_type)
       variables.update(brand_vars)

   # Inject SOT variables if job_id provided
   if job_id:
       sot_vars = await get_source_of_truth_template_vars(job_id)
       variables.update(sot_vars)
   ```

3. In `data/prompts/audience_edit.txt`, add brand voice and SOT sections after line 2 (before TARGET AUDIENCE):
   ```
   == BRAND VOICE ==
   {brand_voice_summary}
   TONE MARKERS: {brand_tone_markers}
   USE PHRASES LIKE: {brand_phrases_to_use}
   AVOID: {brand_phrases_to_avoid}
   VOCABULARY LEVEL: {brand_vocabulary_level}

   == SOURCE CONTEXT ==
   Core Narratives: {core_narratives}
   Primary Pain Point: {primary_pain_point}
   The Promise: {the_promise}

   ```

4. Update the guardrails section (line 34) to reference brand voice:
   Change `- Active voice? (Change passive to active)` section's brand check:
   ```
   - Brand voice aligned? (Matches brand voice summary and tone markers above)
   ```

5. Update `prompt_manager.py` `audience_edit` variables list to include the new vars:
   ```python
   "audience_edit": {
       "model": "gemini-2.5-flash",
       "max_tokens": 8000,
       "variables": [
           "persona_title", "persona_language_level",
           "persona_priorities", "draft_from_step1",
           "brand_voice_summary", "brand_tone_markers",
           "brand_phrases_to_use", "brand_phrases_to_avoid",
           "brand_vocabulary_level",
           "core_narratives", "primary_pain_point", "the_promise",
       ],
   },
   ```

**Verify:** The editing step should now receive brand voice context identical to drafting.py's pattern.

---

## Task 7: H4 — Fix Autopilot Content Fetch

**Files:**
- Modify: `app/services/autopilot.py`

**What to do:**

1. Add `trafilatura` to requirements (check if already there, if not add it).

2. Add a content fetch function before `create_job_from_feed_item()`:
   ```python
   async def fetch_article_content(url: str) -> tuple[str, bool]:
       """
       Fetch article text content from a URL.

       Returns (content, success) tuple.
       """
       try:
           import trafilatura

           async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
               response = await client.get(url)
               if response.status_code != 200:
                   return f"Failed to fetch URL: HTTP {response.status_code}", False

               # Extract article text
               text = trafilatura.extract(response.text)
               if text and len(text.strip()) > 100:
                   return text, True

               # Fallback: use raw text if trafilatura fails
               return response.text[:10000] if response.text else "Could not extract content", False
       except ImportError:
           return "trafilatura not installed", False
       except Exception as e:
           return f"Content fetch error: {str(e)}", False
   ```

3. In `create_job_from_feed_item()`, replace the JSON metadata storage (lines 261-265) with actual content fetching:
   ```python
   # Fetch actual article content instead of storing metadata
   article_content, fetch_success = await fetch_article_content(item['item_url'])

   if not fetch_success:
       # Mark item as failed if content can't be fetched
       await execute(
           db,
           "UPDATE autopilot_items SET processing_status = 'failed' WHERE id = ?",
           (item_id,)
       )
       if not settings.use_postgres:
           await db.commit()
       logger.warning(f"Autopilot: Failed to fetch content for item {item_id}: {article_content}")
       return None
   ```

4. Update the job INSERT to use the fetched content as transcript and store metadata separately:
   ```python
   # Store metadata as JSON in a comment/note, actual content as transcript
   metadata = json.dumps({
       'autopilot_item_id': item_id,
       'source_url': item['item_url'],
       'source_title': item['item_title']
   })
   ```
   Change the `transcript` parameter in the INSERT from the JSON blob to `article_content`.

5. Add `trafilatura` to `requirements.txt` if not present.

**Verify:** After fix, autopilot jobs should contain real article text, not JSON metadata blobs.

---

## Task 8: M2 — Add user_id/job_id to Scoring Function

**Files:**
- Modify: `app/services/scoring.py:12-19, 79-83`
- Modify: `app/services/pipeline_steps.py:379`

**What to do:**

1. In `scoring.py`, add `user_id` and `job_id` parameters to `score_content()`:
   ```python
   async def score_content(
       content: str,
       content_type: str,
       persona_title: str = "",
       brand_voice_summary: str = "",
       brand_tone_markers: str = "",
       brand_phrases_to_avoid: str = "",
       user_id: int = None,
       job_id: str = None,
   ) -> Tuple[dict, float]:
   ```

2. Pass them through to `call_llm_text()` on line 83:
   ```python
   response_text, input_tokens, output_tokens, model_used = await call_llm_text(
       prompt=prompt,
       step="scoring",
       response_format="json",
       user_id=user_id,
       job_id=job_id,
   )
   ```

3. Update `batch_score_content()` to accept and pass through the params:
   ```python
   async def batch_score_content(
       outputs: list[dict],
       persona_title: str = "",
       brand_voice_summary: str = "",
       brand_tone_markers: str = "",
       brand_phrases_to_avoid: str = "",
       user_id: int = None,
       job_id: str = None,
   ) -> Tuple[list[dict], float]:
   ```
   And pass them to `score_content()` on line 137.

4. In `pipeline_steps.py` line 379, update `step_score()` to pass user/job context:
   ```python
   scored_drafts, score_cost = await batch_score_content(
       ctx.drafts, persona_title,
       user_id=ctx.user_id, job_id=ctx.job_id,
   )
   ```

**Verify:** `score_content()` calls include user_id and job_id.

---

## Task 9: M3 — Archive atomization.txt Dead Code

**Files:**
- Move: `data/prompts/atomization.txt` → `data/prompts/archive/atomization.txt`

**What to do:**

1. Create `data/prompts/archive/` directory
2. Move `atomization.txt` to archive
3. Add comment at top: `# ARCHIVED: Replaced by distillation.txt. Original 5-type atom extraction prompt. Do not restore.`

**Verify:** `ls data/prompts/atomization.txt` should fail. `ls data/prompts/archive/atomization.txt` should succeed.

---

## Task 10: M5 — Connect Lifecycle Cron to Scheduler

**Files:**
- Modify: `app/services/scheduler.py`

**What to do:**

The scheduler already exists as `AutopilotScheduler`. Add lifecycle check to its cycle.

1. In `scheduler.py`, import lifecycle at the top of `_check_cycle()` and add it after autopilot checks:
   ```python
   async def _check_cycle(self):
       """Run a single check cycle."""
       from app.services.autopilot import check_due_sources, process_pending_items
       from app.services.lifecycle import check_expiring_stills

       # 1. Check sources that are due for update
       sources_checked = await check_due_sources()
       if sources_checked > 0:
           logger.info(f"Checked {sources_checked} sources")

       # 2. Process pending feed items (create jobs)
       jobs_created = await process_pending_items(limit=3)
       if jobs_created > 0:
           logger.info(f"Created {jobs_created} jobs from feed items")

       # 3. Check for expiring stills (daily - only run once per day)
       if not hasattr(self, '_last_lifecycle_check') or \
          (datetime.utcnow() - self._last_lifecycle_check).total_seconds() > 86400:
           try:
               flagged = await check_expiring_stills()
               if flagged > 0:
                   logger.info(f"Flagged {flagged} expiring stills for review")
               self._last_lifecycle_check = datetime.utcnow()
           except Exception as e:
               logger.error(f"Lifecycle check failed: {e}")
   ```

**Verify:** `check_expiring_stills()` is called from the scheduler loop.

---

## Task 11: M6 — Persona Language Level DB Support

**Files:**
- Modify: `app/services/persona_manager.py:163`
- Modify: `app/api/custom_personas.py`

**What to do:**

1. In `persona_manager.py` line 163, change:
   ```python
   "language_level": "Professional",
   ```
   To:
   ```python
   "language_level": row.get("language_level", "Professional") if hasattr(row, 'get') else (row["language_level"] if "language_level" in row.keys() else "Professional"),
   ```

   Actually simpler — use a try/except pattern:
   ```python
   "language_level": row["language_level"] if "language_level" in (row.keys() if hasattr(row, 'keys') else []) else "Professional",
   ```

   Simplest approach — just try to read it with a fallback:
   ```python
   "language_level": (row["language_level"] or "Professional") if "language_level" in dict(row) else "Professional",
   ```

2. The DB migration (adding the column) should be done manually in SQL:
   ```sql
   ALTER TABLE personas ADD COLUMN language_level VARCHAR(50) DEFAULT 'Professional';
   ```

   Create a migration note but don't auto-run it — note it needs to be run on both SQLite and PostgreSQL.

3. Update `create_persona` endpoint in `custom_personas.py` to accept and store `language_level`.

4. Update the `_row_to_persona_dict` in `custom_personas.py` similarly.

**Verify:** Custom personas can have language_level other than "Professional".

---

## Task 12: L4 — Add quote_stills to Blog Template

**Files:**
- Modify: `data/prompts/blog_draft.txt`
- Modify: `app/services/prompt_manager.py`

**What to do:**

1. In `blog_draft.txt`, after the story stills line (line 23), add:
   ```
   Quote stills: {quote_stills}
   ```

2. In `prompt_manager.py`, add `"quote_stills"` to the blog_draft variables list.

**Note:** The Python code in `drafting.py` line 367 already builds and passes `quote_stills` as a variable — it's just not in the template. This is a one-line template fix.

**Verify:** `{quote_stills}` appears in blog_draft.txt.

---

## Task 13: L6 — Remove Duplicate Brand Voice from LinkedIn Template

**Files:**
- Modify: `data/prompts/linkedin_draft.txt`

**What to do:**

The brand voice section (lines 3-8) in `linkedin_draft.txt` duplicates context that's also injected via the `user_context` block in `drafting.py` line 285. Remove lines 3-8 (the `== BRAND VOICE ==` section) from the template.

Actually wait — looking more carefully, the brand voice template vars are injected INTO the template variables dict (drafting.py:266). The user_context (line 278) is appended as a separate block. So brand voice appears twice: once through template vars filling `{brand_voice_summary}` etc., and once through user_context which calls `get_voice_context_for_drafting()`.

The fix: Remove the `== BRAND VOICE ==` section (lines 3-8) from `linkedin_draft.txt`. The brand voice will still be present via the `user_context` block. Also remove the corresponding variables from the prompt_manager variables list for linkedin_draft.

BUT we need to keep the brand voice vars in the variables list because the SOURCE CONTEXT section (lines 10-14) also uses template vars. Let me reconsider...

Actually the safest fix: Remove only the `== BRAND VOICE ==` section (lines 3-8) from the template. Keep the vars in prompt_manager since other templates still use them and they're needed for the source context section. The brand voice vars will still be passed but just won't have a dedicated section — they'll come through user_context instead.

Wait — also check `email_draft.txt` and `audience_edit.txt` for the same pattern. Email_draft.txt has the same brand voice section (lines 3-8). The audience_edit.txt we're about to ADD brand voice to in Task 6.

For LinkedIn and email: remove the `== BRAND VOICE ==` sections. For blog: same. The user_context block handles brand voice in all drafting functions.

Actually, I need to reconsider. The `== SOURCE CONTEXT ==` section uses `{core_narratives}`, `{primary_pain_point}`, `{the_promise}` — these are injected via `sot_vars`. The `== BRAND VOICE ==` section uses `{brand_voice_summary}`, `{brand_tone_markers}` etc. — these are injected via `brand_vars`. If we remove the brand voice section from the template, those `{var}` placeholders won't be in the template anymore, so the brand_vars won't cause a KeyError (they'll just be unused).

But the user_context from `get_user_context()` includes `get_voice_context_for_drafting()` which provides brand voice as a text block, AND `get_brand_voice_config_context()` which provides the manual config. So brand voice IS already in user_context.

PLUS brand_vars fills `{brand_voice_summary}` etc. in the template. So it appears twice.

The fix: Remove the `== BRAND VOICE ==` template section from linkedin_draft.txt, blog_draft.txt, and email_draft.txt. Keep the SOT section. The brand voice template vars will still be passed but won't error because `str.format()` silently ignores extra kwargs... wait, actually it DOES silently ignore extra kwargs. So removing the section is safe.

Actually no — Python's `str.format()` does NOT silently ignore extra kwargs. It only complains about MISSING keys, not extra ones. So passing extra vars is fine.

Let me simplify: Remove the brand voice block from all 3 drafting templates. Brand voice will come through user_context only.

**Actually, let me re-examine.** The PRD says "Remove the brand voice variables section from the `linkedin_draft.txt` template body (Layer 2). Keep brand voice in the `user_context` block only (Layer 3)." And "Check `audience_edit.txt` and `email_draft.txt` for the same duplication pattern."

So: Remove from linkedin, blog, and email draft templates. DON'T remove from audience_edit since we're ADDING it there (and it won't have user_context).

**Steps:**

1. Remove lines 3-8 (the `== BRAND VOICE ==` block) from `linkedin_draft.txt`
2. Remove lines 3-8 from `blog_draft.txt`
3. Remove lines 3-8 from `email_draft.txt`

**Verify:** Brand voice section appears zero times in linkedin/blog/email draft templates. Output quality maintained via user_context.

---

## Task 14: L5 — Audit Scoring Brand Voice Params

**Files:**
- Modify: `app/services/pipeline_steps.py:368-382`

**What to do:**

1. In `step_score()`, add brand voice loading before the scoring call:
   ```python
   async def step_score(ctx: PipelineContext) -> StepResult:
       """Step 5: Score content quality."""
       await update_job_status(
           ctx.job_id, JobStatus.FACTCHECKING, "Step 5: Scoring content quality", 92, ctx.total_cost
       )
       ctx.total_cost = 0

       # Get persona title for context
       persona = await get_persona(ctx.target_persona, user_id=ctx.user_id)
       persona_title = persona.get("title", "") if persona else ""

       # Load brand voice for scoring context
       from app.services.brand_voice_analyzer import get_brand_voice_template_vars
       brand_vars = await get_brand_voice_template_vars(ctx.user_id)

       scored_drafts, score_cost = await batch_score_content(
           ctx.drafts,
           persona_title,
           brand_voice_summary=brand_vars.get("brand_voice_summary", ""),
           brand_tone_markers=brand_vars.get("brand_tone_markers", ""),
           brand_phrases_to_avoid=brand_vars.get("brand_phrases_to_avoid", ""),
           user_id=ctx.user_id,
           job_id=ctx.job_id,
       )

       ctx.drafts = scored_drafts
       return StepResult(success=True, cost=score_cost)
   ```

**Verify:** `batch_score_content()` is called with explicit brand voice params.

---

## Task 15: L1 — Mark prompt_manager Model Field as Non-Functional

**Files:**
- Modify: `app/services/prompt_manager.py`

**What to do:**

Add a comment to the `default_prompts` dict explaining that the `model` field is metadata-only and the actual model used comes from `ai_model_config`:
```python
# Default prompts with their configurations
# NOTE: The 'model' field here is stored in DB but NOT used for model selection.
# The actual model for each step is configured in ai_model_config table.
# This field is metadata-only for admin UI display.
default_prompts = {
```

This is the minimal fix — just documentation. The admin UI change would require frontend work which is out of scope for the backend sprint.

---

## Task 16: L2 — Extract Email Sequence Prompt to Template File

**Files:**
- Create: `data/prompts/email_sequence_draft.txt`
- Modify: `app/services/drafting.py`
- Modify: `app/services/prompt_manager.py`

**What to do:**

1. Extract the hardcoded prompt from `drafting.py` `draft_email_sequence()` (lines 568-664) into `data/prompts/email_sequence_draft.txt` with proper `{variable}` placeholders.

2. Register in `prompt_manager.py`:
   ```python
   "email_sequence_draft": {
       "model": "claude-opus-4-5-20251101",
       "max_tokens": 8000,
       "variables": [
           "persona_title", "persona_pain_points", "persona_priorities",
           "persona_tone", "all_stills_text",
       ],
   },
   ```

3. Update `draft_email_sequence()` to use `get_rendered_prompt()`.

---

## Task 17: L3 — Extract Hook Generator Prompt to Template File

**Files:**
- Create: `data/prompts/hook_generator.txt`
- Modify: `app/services/hook_generator.py`
- Modify: `app/services/prompt_manager.py`

**What to do:**

1. Extract the hardcoded prompt from `hook_generator.py` `generate_hook_variations()` (lines 58-115) into `data/prompts/hook_generator.txt`.

2. Register in `prompt_manager.py`:
   ```python
   "hook_generator": {
       "model": "gemini-2.5-flash",
       "max_tokens": 4000,
       "variables": [
           "persona_title", "persona_pain_points", "post_content",
       ],
   },
   ```

3. Update `generate_hook_variations()` to use `get_rendered_prompt()`.

---

## Execution Order

Tasks are ordered by dependency and priority:

1. **Task 1** (C1) — Variable names — FIRST, unblocks everything
2. **Task 2** (C2) — Distillation format dedup
3. **Task 3** (M1) — Model default update (quick win)
4. **Task 12** (L4) — Quote stills in blog (quick, related to template work)
5. **Task 13** (L6) — Remove duplicate brand voice from templates
6. **Task 4** (H1) — Sommelier UNION query (biggest visible fix)
7. **Task 5** (H2) — SOT gate verification (already done, just verify)
8. **Task 6** (H3) — Brand voice in editing
9. **Task 7** (H4) — Autopilot content fetch
10. **Task 8** (M2) — Scoring cost attribution
11. **Task 9** (M3) — Archive dead code
12. **Task 10** (M5) — Lifecycle cron
13. **Task 11** (M6) — Persona language level
14. **Task 14** (L5) — Scoring brand voice audit
15. **Task 15** (L1) — Prompt manager model comment
16. **Task 16** (L2) — Email sequence prompt extraction
17. **Task 17** (L3) — Hook generator prompt extraction
