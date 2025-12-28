# AI Workshop Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an AI-powered editing assistant to the Workshop that provides inline suggestions using Gemini 2.5 Flash, with admin-configurable prompts and brand voice integration.

**Architecture:** Side panel in Workshop UI with prompt input, quick action buttons, and persona dropdown. AI returns structured suggestions shown as highlighted expandable blocks. Admin panel section for configuring the editing persona prompt. Uses existing brand voice system.

**Tech Stack:** FastAPI backend, Vanilla JS frontend, SQLite database, OpenRouter (Gemini 2.5 Flash), existing brand voice profiles

---

## Task 1: Database Schema - Add AI Editor Config Table

**Files:**
- Modify: `app/database.py`

**Step 1: Add the ai_editor_config table to the database schema**

Add after the `brand_voice_config` table creation (around line 443):

```python
            -- AI Editor Configuration for Workshop
            CREATE TABLE IF NOT EXISTS ai_editor_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
```

**Step 2: Run the application to trigger database initialization**

Run: `cd /Users/treynortetik/Downloads/Vibe\ Coding\ Projects/content_creation_engine && python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"`

Expected: No errors, table created

---

## Task 2: Backend - Create AI Editor Service

**Files:**
- Create: `app/services/ai_editor.py`

**Step 1: Create the AI editor service with core functions**

```python
"""AI-powered content editor service for Workshop."""
import json
from typing import List, Dict, Optional, Tuple
from app.database import get_db
from app.services.ai_client import call_llm_text
from app.services.brand_voice_analyzer import get_brand_voice_profile
from app.utils.json_parser import parse_llm_json

# Default system prompt for the AI editor
DEFAULT_EDITOR_PROMPT = """You are a skilled content editor helping refine marketing content. Your role is to make LIGHT, targeted edits that improve the content while preserving the author's voice and intent.

EDITING GUIDELINES:
1. Make minimal, surgical edits - never rewrite more than 20-30% of the content
2. Preserve the author's unique voice and style
3. Focus on clarity, impact, and engagement
4. Fix grammar and punctuation errors
5. Improve flow and readability
6. Strengthen hooks and calls-to-action when requested
7. Never add information that wasn't implied in the original
8. Never change the core message or meaning

BRAND VOICE (when provided):
- Match the vocabulary patterns and tone markers
- Use preferred phrases and avoid restricted phrases
- Maintain the specified tone for the platform

OUTPUT FORMAT:
Return a JSON object with an array of suggested edits. Each edit should identify the original text and the suggested replacement, along with a brief explanation.

{
  "suggestions": [
    {
      "id": 1,
      "original_text": "The exact text to replace",
      "suggested_text": "The improved version",
      "explanation": "Brief reason for this change",
      "type": "grammar|clarity|impact|tone|structure"
    }
  ],
  "summary": "Brief overall summary of changes made"
}

IMPORTANT: Only suggest changes that meaningfully improve the content. If the content is already good, return fewer or no suggestions."""


async def get_editor_config() -> Dict[str, str]:
    """Get AI editor configuration from database."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT config_key, config_value FROM ai_editor_config"
        )
        rows = await cursor.fetchall()

        config = {}
        for row in rows:
            config[row["config_key"]] = row["config_value"]

        # Return defaults if not configured
        if "system_prompt" not in config:
            config["system_prompt"] = DEFAULT_EDITOR_PROMPT
        if "model" not in config:
            config["model"] = "google/gemini-2.5-flash-preview"

        return config


async def save_editor_config(config_key: str, config_value: str) -> None:
    """Save AI editor configuration to database."""
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO ai_editor_config (config_key, config_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(config_key) DO UPDATE SET
                config_value = excluded.config_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (config_key, config_value)
        )
        await db.commit()


async def get_ai_edit_suggestions(
    content: str,
    user_prompt: str,
    user_id: int,
    persona_id: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Tuple[Dict, float]:
    """
    Get AI editing suggestions for content.

    Args:
        content: The content to edit
        user_prompt: User's editing instruction (e.g., "make it punchier")
        user_id: User ID for brand voice lookup
        persona_id: Optional target persona ID
        content_type: Optional content type (linkedin, blog, email)

    Returns:
        (suggestions_dict, cost)
    """
    # Get editor config
    config = await get_editor_config()
    system_prompt = config.get("system_prompt", DEFAULT_EDITOR_PROMPT)
    model = config.get("model", "google/gemini-2.5-flash-preview")

    # Get brand voice profile if available
    brand_voice_context = ""
    try:
        profile = await get_brand_voice_profile(user_id)
        if profile:
            brand_voice_context = f"""
BRAND VOICE PROFILE:
- Tone: {profile.get('overall_summary', 'Professional and engaging')}
- Vocabulary Patterns: {json.dumps(profile.get('vocabulary_patterns', {}))}
- Phrases to Use: {json.dumps(profile.get('phrases_to_use', []))}
- Phrases to Avoid: {json.dumps(profile.get('phrases_to_avoid', []))}
"""
    except Exception:
        pass  # Continue without brand voice if lookup fails

    # Get persona context if provided
    persona_context = ""
    if persona_id:
        try:
            from app.services.persona_manager import get_persona
            persona = await get_persona(persona_id, user_id=user_id)
            if persona:
                persona_context = f"""
TARGET PERSONA:
- Title: {persona.get('title', 'General audience')}
- Pain Points: {json.dumps(persona.get('pain_points', []))}
- Goals: {json.dumps(persona.get('goals', []))}
- Preferred Tone: {persona.get('content_preferences', {}).get('tone', 'Professional')}
"""
        except Exception:
            pass

    # Build the full prompt
    full_prompt = f"""{system_prompt}

{brand_voice_context}

{persona_context}

CONTENT TYPE: {content_type or 'general'}

USER REQUEST: {user_prompt}

CONTENT TO EDIT:
{content}

Provide your editing suggestions as valid JSON."""

    # Call the LLM
    response_text, input_tokens, output_tokens, model_used = await call_llm_text(
        prompt=full_prompt,
        step="workshop_ai_edit",  # Custom step name
        max_tokens=2048,
        response_format="json",
    )

    # Parse response
    try:
        result = parse_llm_json(response_text, context="ai_editor")
    except Exception:
        result = {
            "suggestions": [],
            "summary": "Failed to parse AI response",
            "error": True
        }

    # Calculate cost (using Gemini 2.5 Flash pricing)
    from app.services.ai_client import calculate_openrouter_cost
    cost = calculate_openrouter_cost(model_used, input_tokens, output_tokens)

    return result, cost
```

---

## Task 3: Backend - Create Workshop AI Edit API Endpoint

**Files:**
- Modify: `app/api/workshop.py`
- Modify: `app/models/workshop.py`

**Step 1: Add new Pydantic models to workshop.py**

Add at the end of the file:

```python
class AIEditRequest(BaseModel):
    """Request for AI editing suggestions."""
    content: str
    prompt: str
    persona_id: Optional[str] = None
    content_type: Optional[str] = None


class AIEditSuggestion(BaseModel):
    """A single AI edit suggestion."""
    id: int
    original_text: str
    suggested_text: str
    explanation: str
    type: str  # grammar, clarity, impact, tone, structure


class AIEditResponse(BaseModel):
    """Response with AI editing suggestions."""
    suggestions: List[AIEditSuggestion]
    summary: str
    cost: float
```

**Step 2: Add the AI edit endpoint to workshop.py**

Add the import at the top:

```python
from app.services.ai_editor import get_ai_edit_suggestions
```

Add the endpoint after the delete endpoint:

```python
@router.post("/workshop/{output_id}/ai-edit")
async def request_ai_edit(
    output_id: int,
    data: AIEditRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Request AI editing suggestions for workshop content.

    Returns a list of suggested edits that can be accepted/rejected individually.
    """
    async with get_db() as db:
        # Verify ownership
        cursor = await db.execute(
            """
            SELECT o.id, o.content_type
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        content_type = data.content_type or row["content_type"]

    try:
        result, cost = await get_ai_edit_suggestions(
            content=data.content,
            user_prompt=data.prompt,
            user_id=user_id,
            persona_id=data.persona_id,
            content_type=content_type,
        )

        # Format suggestions
        suggestions = []
        for idx, s in enumerate(result.get("suggestions", [])):
            suggestions.append({
                "id": s.get("id", idx + 1),
                "original_text": s.get("original_text", ""),
                "suggested_text": s.get("suggested_text", ""),
                "explanation": s.get("explanation", ""),
                "type": s.get("type", "clarity"),
            })

        return {
            "suggestions": suggestions,
            "summary": result.get("summary", ""),
            "cost": round(cost, 6),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI editing failed: {str(e)}"
        )
```

---

## Task 4: Backend - Add Admin API for AI Editor Config

**Files:**
- Modify: `app/api/admin.py`

**Step 1: Add imports at the top of admin.py**

```python
from app.services.ai_editor import get_editor_config, save_editor_config, DEFAULT_EDITOR_PROMPT
```

**Step 2: Add Pydantic model for AI editor config**

Add after the existing model definitions:

```python
class AIEditorConfigRequest(BaseModel):
    """Request model for updating AI editor config."""
    system_prompt: Optional[str] = None
    model: Optional[str] = None
```

**Step 3: Add the admin endpoints for AI editor config**

Add at the end of the file:

```python
# ========== AI Editor Configuration ==========

@router.get("/ai-editor-config")
async def get_ai_editor_config(_: bool = Depends(verify_admin)):
    """Get AI editor configuration."""
    config = await get_editor_config()
    return {
        "system_prompt": config.get("system_prompt", DEFAULT_EDITOR_PROMPT),
        "model": config.get("model", "google/gemini-2.5-flash-preview"),
        "default_prompt": DEFAULT_EDITOR_PROMPT,
    }


@router.put("/ai-editor-config")
async def update_ai_editor_config(
    request: AIEditorConfigRequest,
    _: bool = Depends(verify_admin),
):
    """Update AI editor configuration."""
    if request.system_prompt is not None:
        await save_editor_config("system_prompt", request.system_prompt)

    if request.model is not None:
        await save_editor_config("model", request.model)

    return {"message": "AI editor configuration saved"}


@router.post("/ai-editor-config/reset")
async def reset_ai_editor_config(_: bool = Depends(verify_admin)):
    """Reset AI editor configuration to defaults."""
    await save_editor_config("system_prompt", DEFAULT_EDITOR_PROMPT)
    await save_editor_config("model", "google/gemini-2.5-flash-preview")
    return {"message": "AI editor configuration reset to defaults"}
```

---

## Task 5: Backend - Register Workshop AI Edit Step with Settings Manager

**Files:**
- Modify: `app/services/settings_manager.py`

**Step 1: Find the get_model_for_step function and add workshop_ai_edit**

Look for the model defaults dictionary and add:

```python
"workshop_ai_edit": "google/gemini-2.5-flash-preview",
```

---

## Task 6: Admin Panel - Add AI Editor Config Section

**Files:**
- Modify: `app/templates/admin/settings.html`

**Step 1: Add the AI Editor Configuration section**

Add after the Model Configuration section (before the closing `</div>` of the grid):

```html
    <!-- AI Editor Configuration -->
    <div class="admin-card border rounded-lg shadow lg:col-span-2">
        <div class="px-6 py-4 border-b" style="border-color: var(--admin-border);">
            <h2 class="text-lg font-semibold">AI Workshop Editor</h2>
            <p class="text-sm" style="color: var(--admin-text-muted);">Configure the AI editing assistant in the Workshop</p>
        </div>
        <div class="p-6 space-y-4">
            <div class="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-4">
                <p class="text-sm text-blue-800">
                    <strong>Workshop AI Editor:</strong> This prompt controls how the AI makes editing suggestions
                    in the Workshop. It uses the user's brand voice profile automatically.
                    Keep edits light and focused - the AI should refine, not rewrite.
                </p>
            </div>

            <div>
                <label class="block text-sm font-medium mb-1" style="color: var(--admin-text);">System Prompt</label>
                <textarea id="ai-editor-prompt" rows="12"
                    class="w-full border rounded px-3 py-2 admin-card font-mono text-sm"
                    style="border-color: var(--admin-border);"
                    placeholder="Loading..."></textarea>
                <p class="text-xs mt-1" style="color: var(--admin-text-muted);">
                    This prompt defines the AI editor's persona and editing guidelines.
                    Brand voice and persona context are added automatically.
                </p>
            </div>

            <div class="flex gap-4 pt-2">
                <button onclick="saveAIEditorConfig()"
                    class="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">
                    Save Configuration
                </button>
                <button onclick="resetAIEditorConfig()"
                    class="px-4 py-2 border rounded hover:opacity-80" style="border-color: var(--admin-border); color: var(--admin-text);">
                    Reset to Default
                </button>
            </div>
        </div>
    </div>
```

**Step 2: Add the JavaScript functions**

Add inside the `{% block scripts %}` section:

```javascript
// AI Editor Config
async function loadAIEditorConfig() {
    try {
        const response = await fetch('/api/admin/ai-editor-config');
        const data = await response.json();
        document.getElementById('ai-editor-prompt').value = data.system_prompt || '';
    } catch (err) {
        console.error('Failed to load AI editor config:', err);
    }
}

async function saveAIEditorConfig() {
    const systemPrompt = document.getElementById('ai-editor-prompt').value;

    try {
        const response = await fetch('/api/admin/ai-editor-config', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ system_prompt: systemPrompt })
        });

        if (response.ok) {
            showSuccess();
        } else {
            showError('Failed to save AI editor configuration');
        }
    } catch (err) {
        showError('Failed to save AI editor configuration');
    }
}

async function resetAIEditorConfig() {
    if (!confirm('Reset AI editor configuration to defaults?')) return;

    try {
        const response = await fetch('/api/admin/ai-editor-config/reset', {
            method: 'POST'
        });

        if (response.ok) {
            await loadAIEditorConfig();
            showSuccess();
        } else {
            showError('Failed to reset configuration');
        }
    } catch (err) {
        showError('Failed to reset configuration');
    }
}

// Load AI editor config on page load
loadAIEditorConfig();
```

---

## Task 7: Frontend - Add AI Editor Side Panel to Workshop

**Files:**
- Modify: `frontend/workshop.html`

**Step 1: Add the AI Editor side panel HTML**

Add after the stills sidebar (before the closing `</div>` of the flex container):

```html
                <!-- AI Editor Sidebar -->
                <div id="ai-editor-sidebar" class="w-96 hidden lg:block">
                    <div class="bg-still-card border border-still-border rounded-lg p-4">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="font-semibold text-still-text">AI Editor</h3>
                            <button onclick="toggleAIEditor()" class="text-still-muted hover:text-still-text">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>

                        <!-- Persona Selector -->
                        <div class="mb-4">
                            <label class="block text-sm text-still-muted mb-1">Target Persona</label>
                            <select id="ai-persona-select" class="w-full bg-still-bg border border-still-border rounded px-3 py-2 text-still-text">
                                <option value="">Use default</option>
                            </select>
                        </div>

                        <!-- Quick Actions -->
                        <div class="mb-4">
                            <label class="block text-sm text-still-muted mb-2">Quick Actions</label>
                            <div class="flex flex-wrap gap-2">
                                <button onclick="quickAIEdit('shorten')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Shorten
                                </button>
                                <button onclick="quickAIEdit('expand')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Expand
                                </button>
                                <button onclick="quickAIEdit('simplify')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Simplify
                                </button>
                                <button onclick="quickAIEdit('punchier')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Punchier
                                </button>
                                <button onclick="quickAIEdit('fix grammar')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Fix Grammar
                                </button>
                                <button onclick="quickAIEdit('improve hook')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Better Hook
                                </button>
                                <button onclick="quickAIEdit('stronger CTA')" class="px-3 py-1 text-xs bg-still-bg border border-still-border rounded hover:border-still-copper">
                                    Stronger CTA
                                </button>
                            </div>
                        </div>

                        <!-- Custom Prompt -->
                        <div class="mb-4">
                            <label class="block text-sm text-still-muted mb-1">Custom Request</label>
                            <textarea id="ai-edit-prompt" rows="2"
                                class="w-full bg-still-bg border border-still-border rounded px-3 py-2 text-still-text text-sm"
                                placeholder="e.g., Make it more conversational..."></textarea>
                            <button onclick="requestAIEdit()" id="ai-edit-btn"
                                class="w-full mt-2 px-4 py-2 bg-still-copper text-white rounded hover:opacity-90 disabled:opacity-50">
                                Get AI Suggestions
                            </button>
                        </div>

                        <!-- Loading State -->
                        <div id="ai-loading" class="hidden text-center py-4">
                            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-still-copper mx-auto"></div>
                            <p class="mt-2 text-sm text-still-muted">Analyzing content...</p>
                        </div>

                        <!-- Suggestions List -->
                        <div id="ai-suggestions" class="space-y-3 max-h-80 overflow-y-auto">
                            <!-- Suggestions will be rendered here -->
                        </div>

                        <!-- Bulk Actions -->
                        <div id="ai-bulk-actions" class="hidden flex gap-2 mt-4 pt-4 border-t border-still-border">
                            <button onclick="acceptAllSuggestions()" class="flex-1 px-3 py-1.5 bg-still-green/20 text-still-green text-sm rounded hover:bg-still-green/30">
                                Accept All
                            </button>
                            <button onclick="rejectAllSuggestions()" class="flex-1 px-3 py-1.5 bg-still-error/20 text-still-error text-sm rounded hover:bg-still-error/30">
                                Reject All
                            </button>
                        </div>
                    </div>
                </div>
```

**Step 2: Add the toggle button in the editor header**

Find the editor action buttons area and add after the "Copy as Markdown" button:

```html
                        <button onclick="toggleAIEditor()" id="btn-ai-editor" class="px-4 py-2 border border-still-copper text-still-copper rounded-lg hover:bg-still-copper/10">
                            AI Editor
                        </button>
```

---

## Task 8: Frontend - Add AI Editor JavaScript Logic

**Files:**
- Modify: `frontend/workshop.html`

**Step 1: Add the AI editor state and functions**

Add to the `<script>` section after the existing state variables:

```javascript
        // AI Editor State
        let aiSuggestions = [];
        let personasList = [];

        // Load personas for dropdown
        async function loadPersonas() {
            try {
                const response = await Auth.fetchWithAuth('/api/personas/all');
                if (response.ok) {
                    const data = await response.json();
                    personasList = data.all_personas || [];
                    populatePersonaDropdown();
                }
            } catch (err) {
                console.error('Failed to load personas:', err);
            }
        }

        function populatePersonaDropdown() {
            const select = document.getElementById('ai-persona-select');
            select.innerHTML = '<option value="">Use default</option>';

            personasList.forEach(p => {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = p.title || p.name;
                select.appendChild(option);
            });
        }

        // Toggle AI editor sidebar
        function toggleAIEditor() {
            const sidebar = document.getElementById('ai-editor-sidebar');
            sidebar.classList.toggle('hidden');

            // Load personas if not already loaded
            if (personasList.length === 0) {
                loadPersonas();
            }
        }

        // Quick edit shortcuts
        function quickAIEdit(action) {
            document.getElementById('ai-edit-prompt').value = action;
            requestAIEdit();
        }

        // Request AI edit suggestions
        async function requestAIEdit() {
            const prompt = document.getElementById('ai-edit-prompt').value.trim();
            if (!prompt) {
                showToast('Please enter an editing request', 'error');
                return;
            }

            const content = document.getElementById('content-editor').value;
            if (!content) {
                showToast('No content to edit', 'error');
                return;
            }

            const personaId = document.getElementById('ai-persona-select').value;

            // Show loading
            document.getElementById('ai-loading').classList.remove('hidden');
            document.getElementById('ai-suggestions').innerHTML = '';
            document.getElementById('ai-bulk-actions').classList.add('hidden');
            document.getElementById('ai-edit-btn').disabled = true;

            try {
                const response = await Auth.fetchWithAuth(`/api/workshop/${currentOutput.id}/ai-edit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content: content,
                        prompt: prompt,
                        persona_id: personaId || null,
                        content_type: currentOutput.content_type
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'AI editing failed');
                }

                const data = await response.json();
                aiSuggestions = data.suggestions || [];

                renderAISuggestions(data);

                if (aiSuggestions.length > 0) {
                    document.getElementById('ai-bulk-actions').classList.remove('hidden');
                    showToast(`${aiSuggestions.length} suggestion(s) found`);
                } else {
                    showToast('No suggestions - content looks good!');
                }

            } catch (err) {
                console.error('AI edit error:', err);
                showToast(err.message || 'AI editing failed', 'error');
            } finally {
                document.getElementById('ai-loading').classList.add('hidden');
                document.getElementById('ai-edit-btn').disabled = false;
            }
        }

        // Render AI suggestions as expandable blocks
        function renderAISuggestions(data) {
            const container = document.getElementById('ai-suggestions');

            if (!aiSuggestions || aiSuggestions.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-4 text-still-muted">
                        <p class="text-sm">${data.summary || 'No suggestions'}</p>
                    </div>
                `;
                return;
            }

            // Summary
            let html = data.summary ? `
                <div class="p-2 bg-still-bg rounded text-sm text-still-muted mb-3">
                    ${escapeHtml(data.summary)}
                </div>
            ` : '';

            // Suggestion blocks
            aiSuggestions.forEach((s, idx) => {
                const typeColors = {
                    grammar: 'bg-blue-900/30 text-blue-400',
                    clarity: 'bg-purple-900/30 text-purple-400',
                    impact: 'bg-amber-900/30 text-amber-400',
                    tone: 'bg-green-900/30 text-green-400',
                    structure: 'bg-pink-900/30 text-pink-400'
                };
                const typeClass = typeColors[s.type] || 'bg-still-border text-still-muted';

                html += `
                    <div class="suggestion-block bg-still-bg rounded-lg p-3 border border-still-border" data-idx="${idx}">
                        <div class="flex items-center justify-between mb-2">
                            <span class="px-2 py-0.5 ${typeClass} text-xs rounded">${s.type}</span>
                            <div class="flex gap-1">
                                <button onclick="acceptSuggestion(${idx})" class="p-1 text-still-green hover:bg-still-green/20 rounded" title="Accept">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                    </svg>
                                </button>
                                <button onclick="rejectSuggestion(${idx})" class="p-1 text-still-error hover:bg-still-error/20 rounded" title="Reject">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <div class="text-xs text-still-muted mb-2">${escapeHtml(s.explanation)}</div>
                        <div class="space-y-2">
                            <div class="p-2 bg-still-error/10 rounded text-sm">
                                <span class="text-still-error line-through">${escapeHtml(s.original_text)}</span>
                            </div>
                            <div class="p-2 bg-still-green/10 rounded text-sm">
                                <span class="text-still-green">${escapeHtml(s.suggested_text)}</span>
                            </div>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        }

        // Accept a single suggestion
        function acceptSuggestion(idx) {
            const suggestion = aiSuggestions[idx];
            if (!suggestion) return;

            const editor = document.getElementById('content-editor');
            const content = editor.value;

            // Replace the original text with the suggested text
            const newContent = content.replace(suggestion.original_text, suggestion.suggested_text);

            if (newContent !== content) {
                editor.value = newContent;
                handleEditorInput();
                showToast('Suggestion applied');
            } else {
                showToast('Could not find text to replace', 'error');
            }

            // Remove this suggestion from the list
            removeSuggestion(idx);
        }

        // Reject a single suggestion
        function rejectSuggestion(idx) {
            removeSuggestion(idx);
            showToast('Suggestion rejected');
        }

        // Remove suggestion from list
        function removeSuggestion(idx) {
            aiSuggestions.splice(idx, 1);
            renderAISuggestions({ suggestions: aiSuggestions, summary: '' });

            if (aiSuggestions.length === 0) {
                document.getElementById('ai-bulk-actions').classList.add('hidden');
            }
        }

        // Accept all suggestions
        function acceptAllSuggestions() {
            const editor = document.getElementById('content-editor');
            let content = editor.value;
            let appliedCount = 0;

            // Apply all suggestions
            aiSuggestions.forEach(s => {
                const newContent = content.replace(s.original_text, s.suggested_text);
                if (newContent !== content) {
                    content = newContent;
                    appliedCount++;
                }
            });

            editor.value = content;
            handleEditorInput();

            // Clear suggestions
            aiSuggestions = [];
            renderAISuggestions({ suggestions: [], summary: '' });
            document.getElementById('ai-bulk-actions').classList.add('hidden');

            showToast(`Applied ${appliedCount} suggestion(s)`);
        }

        // Reject all suggestions
        function rejectAllSuggestions() {
            aiSuggestions = [];
            renderAISuggestions({ suggestions: [], summary: '' });
            document.getElementById('ai-bulk-actions').classList.add('hidden');
            showToast('All suggestions rejected');
        }
```

**Step 2: Initialize personas on editor open**

In the `openEditor` function, add after setting up the editor:

```javascript
                // Clear AI suggestions when opening new content
                aiSuggestions = [];
                document.getElementById('ai-suggestions').innerHTML = '';
                document.getElementById('ai-bulk-actions').classList.add('hidden');
                document.getElementById('ai-edit-prompt').value = '';
```

---

## Task 9: Add Model Config for Workshop AI Edit Step

**Files:**
- Modify: `app/services/settings_manager.py`

**Step 1: Find and update the model defaults or get_model_for_step function**

Add "workshop_ai_edit" to the PIPELINE_SERVICES list or default models dictionary:

```python
"workshop_ai_edit": "google/gemini-2.5-flash-preview",
```

---

## Task 10: Testing and Verification

**Step 1: Run the application**

```bash
cd /Users/treynortetik/Downloads/Vibe\ Coding\ Projects/content_creation_engine
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

**Step 2: Verify database table creation**

Check that `ai_editor_config` table exists.

**Step 3: Test admin panel**

1. Go to `/admin/settings`
2. Verify the "AI Workshop Editor" section appears
3. Test saving and resetting the prompt

**Step 4: Test workshop AI editing**

1. Go to `/workshop.html`
2. Open a piece of content
3. Click "AI Editor" button
4. Enter a prompt like "make it punchier"
5. Verify suggestions appear
6. Test accept/reject individual suggestions
7. Test accept all/reject all

---

## Summary

This implementation adds:
1. Database table for AI editor configuration
2. Backend service for AI editing with brand voice integration
3. API endpoint for requesting AI edits
4. Admin panel section for configuring the AI editor prompt
5. Workshop UI with side panel, quick actions, persona selector, and inline suggestions

The AI editor uses Gemini 2.5 Flash via OpenRouter and integrates with the existing brand voice system.
