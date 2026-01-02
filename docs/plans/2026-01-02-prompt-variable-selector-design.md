# Prompt Variable Selector Design

## Overview

Add a variable selection UI to the prompt editor that allows admins to select which variables are injected into each prompt. Also consolidate all prompt editing (including AI Workshop Editor and Sommelier) into a single Prompt Editor tab.

## Changes

### 1. UI - Variable Selector Component

Each prompt in the editor gets a collapsible variable selector below the textarea:

```
Selected: [persona_title] [brand_tone] [selected_atoms]

▼ Persona (2/6)
  ☑ persona_title  ☑ persona_pain_points
  ☐ persona_priorities  ☐ persona_language_level
  ☐ persona_industry  ☐ persona_content_preferences

▶ Brand Voice (1/9) - collapsed
▶ Memory & Style (0/2) - collapsed
▶ Content/Stills (1/9) - collapsed
▶ Drafts (0/3) - collapsed
▶ Campaign (0/2) - collapsed
```

### 2. Master Variable List

**Persona** (6 vars):
- `persona_title`, `persona_pain_points`, `persona_priorities`
- `persona_language_level`, `persona_industry`, `persona_content_preferences`

**Brand Voice** (9 vars):
- `brand_company_name`, `brand_mission`, `brand_differentiators`
- `brand_tone`, `brand_vocabulary_level`, `brand_phrases_to_use`
- `brand_phrases_to_avoid`, `brand_voice_summary`, `brand_tone_markers`

**Memory & Style** (2 vars):
- `memory_rules`, `style_dna`

**Content/Stills** (9 vars):
- `cleaned_transcript`, `source_summary`, `selected_atoms`
- `problem_atoms`, `insight_atoms`, `solution_atoms`
- `data_atoms`, `story_atoms`, `quote_atoms`

**Drafts** (3 vars):
- `draft_from_step1`, `edited_draft_from_step2`, `original_transcript`

**Campaign** (2 vars):
- `campaign_name`, `magic_words`

### 3. Move AI Workshop + Sommelier to Prompt Editor

Remove these sections from Settings tab:
- AI Workshop Editor (system_prompt)
- Sommelier Configuration (parse_prompt, rerank_prompt)

Add to Prompt Editor sidebar under a separator:
- `ai_workshop` - System prompt for Workshop AI
- `sommelier_query_parse` - Query parsing prompt
- `sommelier_rerank` - Result reranking prompt

These will continue to use `ai_editor_config` table for storage but appear in the unified prompt editor.

### 4. Backend Changes

**New endpoint: `GET /api/admin/prompt-variables`**
Returns the master list of available variables with categories.

**Updated endpoint: `PUT /api/admin/prompts/{template_name}`**
Add `variables: List[str]` parameter to save selected variables.

**New endpoints for special prompts:**
- `PUT /api/admin/ai-editor-config` - Add variables support
- `PUT /api/admin/sommelier-config` - Add variables support

### 5. Files to Modify

- `app/api/admin.py` - Add new endpoints, update existing
- `app/templates/admin/prompt_editor.html` - Major UI overhaul
- `app/templates/admin/settings.html` - Remove AI Workshop/Sommelier sections

## Implementation Notes

- Variables are stored as JSON array in `variables` column (existing)
- AI Workshop/Sommelier variables stored as `{config_key}_variables` in `ai_editor_config`
- Category collapse state persists in localStorage
- Unsaved changes show indicator on Save button
