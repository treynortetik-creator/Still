# Brand Voice Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the existing `brand_voice_config` database table to the content generation pipeline and create a UI for users to configure their brand voice per content type (LinkedIn, Blog, Email).

**Architecture:** Add a new function `get_brand_voice_config_context()` that retrieves the user's brand voice configuration and formats it for prompt injection. Modify `get_user_context()` to accept a content_type parameter and include the brand voice config. Redesign the Brand Voice tab in settings.html with a form to save master voice + per-platform tones.

**Tech Stack:** Python/FastAPI (backend), vanilla JavaScript (frontend), SQLite (database), Tailwind CSS (styling)

---

## Task 1: Add Brand Voice Config Context Function

**Files:**
- Modify: `app/services/brand_voice_analyzer.py` (add function at end of file)

**Step 1: Add the `get_brand_voice_config_context` function**

Add this function to the end of `app/services/brand_voice_analyzer.py`:

```python
async def get_brand_voice_config_context(user_id: int, content_type: str = None) -> str:
    """
    Get brand voice configuration to inject into drafting prompts.

    Args:
        user_id: User ID
        content_type: "linkedin", "blog", or "email" for platform-specific tone

    Returns:
        Formatted context string for prompt injection
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT company_name, industry, tone_linkedin, tone_blog,
                   tone_email, core_principles, phrases_to_use,
                   phrases_to_avoid, vocabulary_level
            FROM brand_voice_config
            WHERE user_id = ?
            """,
            (user_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return ""

        # Check if any meaningful data exists
        has_data = any([
            row["company_name"],
            row["industry"],
            row["core_principles"],
            row["phrases_to_use"],
            row["phrases_to_avoid"],
            row["tone_linkedin"],
            row["tone_blog"],
            row["tone_email"],
        ])

        if not has_data:
            return ""

        context_parts = ["\n=== BRAND VOICE GUIDELINES (apply to all content) ==="]

        if row["company_name"]:
            context_parts.append(f"COMPANY: {row['company_name']}")

        if row["industry"]:
            context_parts.append(f"INDUSTRY: {row['industry']}")

        if row["vocabulary_level"]:
            context_parts.append(f"VOCABULARY LEVEL: {row['vocabulary_level'].title()}")

        # Core principles
        if row["core_principles"]:
            principles = json.loads(row["core_principles"])
            if principles:
                context_parts.append("\nCORE PRINCIPLES:")
                for principle in principles:
                    context_parts.append(f"- {principle}")

        # Phrases to use
        if row["phrases_to_use"]:
            phrases = json.loads(row["phrases_to_use"])
            if phrases:
                context_parts.append(f"\nUSE THESE PHRASES: {'; '.join(phrases)}")

        # Phrases to avoid
        if row["phrases_to_avoid"]:
            avoid = json.loads(row["phrases_to_avoid"])
            if avoid:
                context_parts.append(f"AVOID THESE PHRASES: {'; '.join(avoid)}")

        # Platform-specific tone
        tone_map = {
            "linkedin": row["tone_linkedin"],
            "blog": row["tone_blog"],
            "email": row["tone_email"],
        }

        if content_type and content_type in tone_map and tone_map[content_type]:
            platform_name = content_type.title()
            context_parts.append(f"\nPLATFORM-SPECIFIC TONE ({platform_name}):")
            context_parts.append(tone_map[content_type])

        context_parts.append("")

        return "\n".join(context_parts)
```

**Step 2: Verify the function is syntactically correct**

Run: `python -c "import app.services.brand_voice_analyzer; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/services/brand_voice_analyzer.py
git commit -m "feat: add get_brand_voice_config_context for pipeline injection"
```

---

## Task 2: Update get_user_context to Accept Content Type

**Files:**
- Modify: `app/services/drafting.py` (lines 14-49)

**Step 1: Update the `get_user_context` function signature and body**

Replace the existing `get_user_context` function (lines 14-49) with:

```python
async def get_user_context(user_id: int, content_type: str = None) -> str:
    """
    Get user-specific context to inject into drafting prompts.

    Includes memory rules, style DNA, brand voice profile, and brand voice config.

    Args:
        user_id: User ID
        content_type: Optional content type ("linkedin", "blog", "email") for
                      platform-specific brand voice tone
    """
    context_parts = []

    try:
        # Memory rules
        from app.api.memory import get_memory_rules_context
        memory_context = await get_memory_rules_context(user_id)
        if memory_context:
            context_parts.append(memory_context)
    except Exception as e:
        logger.warning(f"Memory context failed for user {user_id}: {e}")

    try:
        # Style DNA from swipes
        from app.services.swipe_analyzer import get_style_context_for_drafting
        style_context = await get_style_context_for_drafting(user_id)
        if style_context:
            context_parts.append(style_context)
    except Exception as e:
        logger.warning(f"Style context failed for user {user_id}: {e}")

    try:
        # Brand voice profile (AI-analyzed from samples)
        from app.services.brand_voice_analyzer import get_voice_context_for_drafting
        voice_context = await get_voice_context_for_drafting(user_id)
        if voice_context:
            context_parts.append(voice_context)
    except Exception as e:
        logger.warning(f"Brand voice context failed for user {user_id}: {e}")

    try:
        # Brand voice config (manual settings with per-platform tones)
        from app.services.brand_voice_analyzer import get_brand_voice_config_context
        config_context = await get_brand_voice_config_context(user_id, content_type)
        if config_context:
            context_parts.append(config_context)
    except Exception as e:
        logger.warning(f"Brand voice config context failed for user {user_id}: {e}")

    return "\n".join(context_parts)
```

**Step 2: Verify the module loads correctly**

Run: `python -c "import app.services.drafting; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/services/drafting.py
git commit -m "feat: add content_type param to get_user_context for platform-specific voice"
```

---

## Task 3: Update LinkedIn Drafting to Pass Content Type

**Files:**
- Modify: `app/services/drafting.py` (line 93)

**Step 1: Update the `get_user_context` call in `draft_linkedin_posts`**

Find this line (around line 91-93):
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id)
```

Replace with:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="linkedin")
```

**Step 2: Commit**

```bash
git add app/services/drafting.py
git commit -m "feat: pass linkedin content_type to get_user_context"
```

---

## Task 4: Update Blog Drafting to Pass Content Type

**Files:**
- Modify: `app/services/drafting.py` (around line 184-185)

**Step 1: Update the `get_user_context` call in `draft_blog_post`**

Find this line:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id)
```

Replace with:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="blog")
```

**Step 2: Commit**

```bash
git add app/services/drafting.py
git commit -m "feat: pass blog content_type to get_user_context"
```

---

## Task 5: Update Email Drafting to Pass Content Type

**Files:**
- Modify: `app/services/drafting.py` (around line 252-253)

**Step 1: Update the `get_user_context` call in `draft_email`**

Find this line:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id)
```

Replace with:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="email")
```

**Step 2: Commit**

```bash
git add app/services/drafting.py
git commit -m "feat: pass email content_type to get_user_context"
```

---

## Task 6: Update Email Sequence Drafting to Pass Content Type

**Files:**
- Modify: `app/services/drafting.py` (around line 341-342)

**Step 1: Update the `get_user_context` call in `draft_email_sequence`**

Find this line:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id)
```

Replace with:
```python
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="email")
```

**Step 2: Commit**

```bash
git add app/services/drafting.py
git commit -m "feat: pass email content_type to get_user_context for sequences"
```

---

## Task 7: Redesign Brand Voice Tab in Settings UI

**Files:**
- Modify: `frontend/settings.html` (replace Brand Voice tab content, lines 205-251)

**Step 1: Replace the Brand Voice tab HTML**

Find the brand-voice-tab div (id="brand-voice-tab") and replace the entire div with:

```html
        <!-- Brand Voice Tab -->
        <div id="brand-voice-tab" class="hidden space-y-6">
            <!-- Master Voice Section -->
            <div class="bg-still-card rounded-lg shadow-sm p-6 border border-still-border">
                <h2 class="text-xl font-semibold mb-2 text-still-text">Master Brand Voice</h2>
                <p class="text-still-muted text-sm mb-6">
                    Define your core brand identity. These settings apply to all content types.
                </p>

                <div class="grid md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-still-text mb-2">Company/Brand Name</label>
                        <input type="text" id="bv-company-name"
                            class="w-full input-premium"
                            placeholder="e.g., Acme Healthcare">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-still-text mb-2">Industry</label>
                        <input type="text" id="bv-industry"
                            class="w-full input-premium"
                            placeholder="e.g., Healthcare Technology">
                    </div>
                </div>

                <div class="mt-6">
                    <label class="block text-sm font-medium text-still-text mb-2">Vocabulary Level</label>
                    <select id="bv-vocabulary" class="w-full input-premium select-premium">
                        <option value="casual">Casual - everyday language, conversational</option>
                        <option value="professional" selected>Professional - business appropriate</option>
                        <option value="technical">Technical - industry jargon acceptable</option>
                    </select>
                </div>

                <div class="mt-6">
                    <label class="block text-sm font-medium text-still-text mb-2">Core Principles</label>
                    <p class="text-xs text-still-disabled mb-2">What does your brand stand for? (one per line)</p>
                    <textarea id="bv-core-principles" rows="4"
                        class="w-full bg-still-bg border border-still-border rounded-lg p-3 text-still-text focus:ring-2 focus:ring-still-copper"
                        placeholder="Clarity over jargon&#10;Lead with value, not features&#10;Speak to outcomes"></textarea>
                </div>

                <div class="grid md:grid-cols-2 gap-6 mt-6">
                    <div>
                        <label class="block text-sm font-medium text-still-text mb-2">Phrases to Use</label>
                        <p class="text-xs text-still-disabled mb-2">Signature expressions (one per line)</p>
                        <textarea id="bv-phrases-use" rows="4"
                            class="w-full bg-still-bg border border-still-border rounded-lg p-3 text-still-text focus:ring-2 focus:ring-still-copper"
                            placeholder="Here's the thing&#10;What this means for you&#10;The real challenge is"></textarea>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-still-text mb-2">Phrases to Avoid</label>
                        <p class="text-xs text-still-disabled mb-2">Words that don't fit your brand (one per line)</p>
                        <textarea id="bv-phrases-avoid" rows="4"
                            class="w-full bg-still-bg border border-still-border rounded-lg p-3 text-still-text focus:ring-2 focus:ring-still-copper"
                            placeholder="Synergy&#10;Circle back&#10;Low-hanging fruit"></textarea>
                    </div>
                </div>
            </div>

            <!-- Platform-Specific Tones -->
            <div class="bg-still-card rounded-lg shadow-sm p-6 border border-still-border">
                <h2 class="text-xl font-semibold mb-2 text-still-text">Platform-Specific Tones</h2>
                <p class="text-still-muted text-sm mb-6">
                    Customize how your brand voice adapts to each content type.
                </p>

                <div class="space-y-6">
                    <!-- LinkedIn -->
                    <div class="p-4 bg-still-bg rounded-lg border border-still-border">
                        <div class="flex items-center gap-3 mb-3">
                            <div class="w-10 h-10 rounded-lg bg-[#0A66C2]/20 flex items-center justify-center">
                                <svg class="w-5 h-5 text-[#0A66C2]" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-semibold text-still-text">LinkedIn</h3>
                                <p class="text-xs text-still-muted">Professional networking, thought leadership</p>
                            </div>
                        </div>
                        <textarea id="bv-tone-linkedin" rows="3"
                            class="w-full bg-still-card border border-still-border rounded-lg p-3 text-still-text focus:ring-2 focus:ring-still-copper"
                            placeholder="e.g., Punchy and data-driven. Lead with insights. Position as thought leadership. Keep paragraphs short (2-3 lines max). Use statistics when available."></textarea>
                    </div>

                    <!-- Blog -->
                    <div class="p-4 bg-still-bg rounded-lg border border-still-border">
                        <div class="flex items-center gap-3 mb-3">
                            <div class="w-10 h-10 rounded-lg bg-still-green/20 flex items-center justify-center">
                                <svg class="w-5 h-5 text-still-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-semibold text-still-text">Blog Posts</h3>
                                <p class="text-xs text-still-muted">Educational content, SEO, detailed exploration</p>
                            </div>
                        </div>
                        <textarea id="bv-tone-blog" rows="3"
                            class="w-full bg-still-card border border-still-border rounded-lg p-3 text-still-text focus:ring-2 focus:ring-still-copper"
                            placeholder="e.g., Educational and engaging. Use storytelling with real examples. Include actionable takeaways. Aim for comprehensive depth while remaining accessible."></textarea>
                    </div>

                    <!-- Email -->
                    <div class="p-4 bg-still-bg rounded-lg border border-still-border">
                        <div class="flex items-center gap-3 mb-3">
                            <div class="w-10 h-10 rounded-lg bg-still-copper/20 flex items-center justify-center">
                                <svg class="w-5 h-5 text-still-copper" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                                </svg>
                            </div>
                            <div>
                                <h3 class="font-semibold text-still-text">Email</h3>
                                <p class="text-xs text-still-muted">Direct communication, newsletters, sequences</p>
                            </div>
                        </div>
                        <textarea id="bv-tone-email" rows="3"
                            class="w-full bg-still-card border border-still-border rounded-lg p-3 text-still-text focus:ring-2 focus:ring-still-copper"
                            placeholder="e.g., Direct and personal. Write like you're talking to one person. Get to the point quickly. Always include a clear call to action."></textarea>
                    </div>
                </div>
            </div>

            <!-- Save Button -->
            <div class="flex justify-end">
                <button onclick="saveBrandVoiceConfig()" class="btn btn-primary text-white px-8 py-3 rounded-lg font-semibold">
                    Save Brand Voice Settings
                </button>
            </div>

            <!-- AI Analysis Section (collapsed) -->
            <details class="bg-still-card rounded-lg shadow-sm border border-still-border">
                <summary class="p-6 cursor-pointer text-still-text font-semibold">
                    AI Voice Analysis (from writing samples)
                </summary>
                <div class="px-6 pb-6 pt-2 border-t border-still-border">
                    <p class="text-still-muted text-sm mb-4">
                        Optionally, upload samples of your own writing to let AI analyze your natural voice patterns.
                    </p>

                    <!-- Upload Samples -->
                    <div class="mb-6">
                        <label class="block text-sm font-medium text-still-text mb-2">Paste a content sample</label>
                        <textarea id="voice-sample" rows="4"
                            class="w-full bg-still-bg border border-still-border rounded-lg p-3 text-still-text placeholder-still-disabled focus:ring-2 focus:ring-still-copper"
                            placeholder="Paste a LinkedIn post, blog excerpt, or email you've written..."></textarea>
                        <div class="flex gap-2 mt-2">
                            <select id="sample-type" class="input-premium select-premium">
                                <option value="linkedin">LinkedIn Post</option>
                                <option value="blog">Blog Post</option>
                                <option value="email">Email</option>
                                <option value="other">Other</option>
                            </select>
                            <button onclick="addVoiceSample()" class="bg-still-border text-still-text px-4 py-2 rounded-lg hover:bg-still-muted/20">
                                Add Sample
                            </button>
                        </div>
                    </div>

                    <!-- Samples List -->
                    <div id="voice-samples-list" class="space-y-2 mb-6">
                        <!-- Populated by JS -->
                    </div>

                    <!-- Analyze Button -->
                    <button id="analyze-voice-btn" onclick="analyzeVoice()" disabled
                        class="w-full btn btn-primary text-white py-3 rounded-lg font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed">
                        Analyze My Voice (need 3+ samples)
                    </button>

                    <!-- Voice Profile -->
                    <div id="voice-profile" class="hidden mt-6 p-4 bg-still-copper/10 rounded-lg border border-still-copper/30">
                        <h3 class="font-semibold text-still-copper mb-3">Your Analyzed Voice Profile</h3>
                        <div id="voice-profile-content" class="text-sm text-still-copper/80 space-y-3">
                            <!-- Populated by JS -->
                        </div>
                    </div>
                </div>
            </details>
        </div>
```

**Step 2: Commit**

```bash
git add frontend/settings.html
git commit -m "feat: redesign brand voice tab with master voice and platform tones"
```

---

## Task 8: Add JavaScript Functions for Brand Voice Config

**Files:**
- Modify: `frontend/settings.html` (add JS functions in script section)

**Step 1: Add load and save functions for brand voice config**

Find the `// ============ Brand Voice ============` section in the script and add these functions after `analyzeVoice()`:

```javascript
        // ============ Brand Voice Config ============
        async function loadBrandVoiceConfig() {
            try {
                const response = await Auth.fetchWithAuth('/api/brand-voice/config');
                if (response.ok) {
                    const data = await response.json();

                    document.getElementById('bv-company-name').value = data.company_name || '';
                    document.getElementById('bv-industry').value = data.industry || '';
                    document.getElementById('bv-vocabulary').value = data.vocabulary_level || 'professional';
                    document.getElementById('bv-core-principles').value = (data.core_principles || []).join('\n');
                    document.getElementById('bv-phrases-use').value = (data.phrases_to_use || []).join('\n');
                    document.getElementById('bv-phrases-avoid').value = (data.phrases_to_avoid || []).join('\n');
                    document.getElementById('bv-tone-linkedin').value = data.tone_linkedin || '';
                    document.getElementById('bv-tone-blog').value = data.tone_blog || '';
                    document.getElementById('bv-tone-email').value = data.tone_email || '';
                }
            } catch (err) {
                console.log('No brand voice config yet');
            }
        }

        async function saveBrandVoiceConfig() {
            const corePrinciples = document.getElementById('bv-core-principles').value
                .split('\n')
                .map(s => s.trim())
                .filter(s => s.length > 0);

            const phrasesToUse = document.getElementById('bv-phrases-use').value
                .split('\n')
                .map(s => s.trim())
                .filter(s => s.length > 0);

            const phrasesToAvoid = document.getElementById('bv-phrases-avoid').value
                .split('\n')
                .map(s => s.trim())
                .filter(s => s.length > 0);

            const configData = {
                company_name: document.getElementById('bv-company-name').value.trim() || null,
                industry: document.getElementById('bv-industry').value.trim() || null,
                vocabulary_level: document.getElementById('bv-vocabulary').value,
                core_principles: corePrinciples.length > 0 ? corePrinciples : null,
                phrases_to_use: phrasesToUse.length > 0 ? phrasesToUse : null,
                phrases_to_avoid: phrasesToAvoid.length > 0 ? phrasesToAvoid : null,
                tone_linkedin: document.getElementById('bv-tone-linkedin').value.trim() || null,
                tone_blog: document.getElementById('bv-tone-blog').value.trim() || null,
                tone_email: document.getElementById('bv-tone-email').value.trim() || null,
            };

            try {
                const response = await Auth.fetchWithAuth('/api/brand-voice/config', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(configData)
                });

                if (response.ok) {
                    showToast('Brand voice settings saved!');
                } else {
                    const err = await response.json();
                    showToast(err.detail || 'Failed to save', 'error');
                }
            } catch (err) {
                showToast('Error saving brand voice settings');
            }
        }
```

**Step 2: Update the tab switching to load brand voice config**

Find this line in the tab switching code:
```javascript
                if (tab === 'brand-voice') loadVoiceProfile();
```

Replace with:
```javascript
                if (tab === 'brand-voice') {
                    loadBrandVoiceConfig();
                    loadVoiceProfile();
                }
```

**Step 3: Commit**

```bash
git add frontend/settings.html
git commit -m "feat: add JS functions to load/save brand voice config"
```

---

## Task 9: Test the Complete Integration

**Step 1: Start the server**

Run: `cd "/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine" && python -m uvicorn app.main:app --reload --port 5001`

**Step 2: Manual test checklist**

1. Navigate to http://localhost:5001/settings.html
2. Click on "Brand Voice" tab
3. Fill in master voice fields:
   - Company Name: "Test Company"
   - Industry: "Technology"
   - Core Principles: "Be clear\nBe helpful"
   - Phrases to Use: "Here's the thing"
   - Phrases to Avoid: "Synergy"
4. Fill in platform tones:
   - LinkedIn: "Punchy and professional"
   - Blog: "Educational and detailed"
   - Email: "Direct and personal"
5. Click "Save Brand Voice Settings"
6. Verify toast shows "Brand voice settings saved!"
7. Refresh page, click Brand Voice tab, verify all fields are populated

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete brand voice config integration with pipeline"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `app/services/brand_voice_analyzer.py` | Added `get_brand_voice_config_context()` function |
| `app/services/drafting.py` | Updated `get_user_context()` to accept content_type, updated all 4 drafting functions to pass content type |
| `frontend/settings.html` | Redesigned Brand Voice tab with config form, added load/save JS functions |

## Verification

After implementation, the brand voice config will be injected into content generation:
- LinkedIn posts get master voice + `tone_linkedin`
- Blog posts get master voice + `tone_blog`
- Emails/sequences get master voice + `tone_email`
