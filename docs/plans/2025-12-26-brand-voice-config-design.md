# Brand Voice Configuration - Design Document

**Date:** 2025-12-26
**Status:** Approved for Implementation

## Problem Statement

The brand voice configuration system exists in the database (`brand_voice_config` table) but is not connected to the content generation pipeline. Users cannot:
1. Configure their brand voice through the UI
2. Have their brand voice settings applied to generated content
3. Customize tone per content type (LinkedIn, Blog, Email)

## Solution: Master Voice + Content-Type Overrides

### Architecture

One core brand voice profile that applies everywhere, plus content-type-specific tone overrides.

```
┌─────────────────────────────────────────────────────────────┐
│                    MASTER BRAND VOICE                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Company Name: "Acme Corp"                            │    │
│  │ Industry: "Healthcare Technology"                    │    │
│  │ Core Principles: ["Clarity over jargon", ...]        │    │
│  │ Phrases to Use: ["Here's the thing", ...]            │    │
│  │ Phrases to Avoid: ["Synergy", "Circle back", ...]    │    │
│  │ Vocabulary Level: "Professional"                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  LinkedIn   │  │    Blog     │  │    Email    │         │
│  │─────────────│  │─────────────│  │─────────────│         │
│  │ Punchy,     │  │ Educational,│  │ Direct,     │         │
│  │ data-driven,│  │ storytelling│  │ personal,   │         │
│  │ thought     │  │ with depth  │  │ action-     │         │
│  │ leadership  │  │             │  │ oriented    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Upload/Reserve → Pipeline → draft_linkedin_posts(user_id)
                                    ↓
                         get_user_context(user_id, "linkedin")
                                    ↓
                    ┌─────────────────────────────────────┐
                    │ 1. Memory Rules                     │
                    │ 2. Style DNA (from swipes)          │
                    │ 3. Brand Voice Profile (AI-analyzed)│
                    │ 4. Brand Voice Config (manual) ←NEW │
                    │    - Core principles                │
                    │    - Phrases to use/avoid           │
                    │    - LinkedIn-specific tone         │
                    └─────────────────────────────────────┘
                                    ↓
                         Injected into LLM prompt
```

## Implementation Components

### 1. Backend Changes

#### A. New function in `brand_voice_analyzer.py`
```python
async def get_brand_voice_config_context(user_id: int, content_type: str = None) -> str:
    """
    Get brand voice config to inject into drafting prompts.

    Args:
        user_id: User ID
        content_type: "linkedin", "blog", or "email" for platform-specific tone

    Returns:
        Formatted context string for prompt injection
    """
```

#### B. Modify `get_user_context()` in `drafting.py`
- Add `content_type` parameter
- Call `get_brand_voice_config_context(user_id, content_type)`
- Append to existing context

#### C. Update drafting functions
- `draft_linkedin_posts()` → pass `content_type="linkedin"`
- `draft_blog_post()` → pass `content_type="blog"`
- `draft_email()` → pass `content_type="email"`
- `draft_email_sequence()` → pass `content_type="email"`

### 2. Frontend Changes

#### A. Redesign Brand Voice Tab in `settings.html`

**Master Voice Section:**
- Company Name (text input)
- Industry (text input)
- Core Principles (textarea, one per line)
- Phrases to Use (textarea, one per line)
- Phrases to Avoid (textarea, one per line)
- Vocabulary Level (dropdown: casual/professional/technical)

**Content-Type Cards:**
Three cards for LinkedIn, Blog, Email with:
- Platform icon and name
- Tone description (textarea)
- Example of how this tone sounds (helper text)

**Save Button:**
- Calls `PUT /api/brand-voice/config`
- Shows success toast

### 3. Context Injection Format

The injected context will look like:

```
=== BRAND VOICE GUIDELINES (apply to all content) ===
COMPANY: Acme Healthcare
INDUSTRY: Healthcare Technology
VOCABULARY LEVEL: Professional

CORE PRINCIPLES:
- Clarity over jargon
- Lead with value, not features
- Speak to outcomes, not processes

USE THESE PHRASES: "Here's the thing"; "What this means for you"; "The real challenge is"
AVOID THESE PHRASES: "Synergy"; "Circle back"; "Touch base"; "Low-hanging fruit"

PLATFORM-SPECIFIC TONE (LinkedIn):
Write in a punchy, data-driven style. Lead with insights. Position as thought leadership.
Keep paragraphs short. Use numbers and statistics when available.
```

## Database Schema

Already exists in `brand_voice_config` table:
- `user_id` (FK to users)
- `company_name` (TEXT)
- `industry` (TEXT)
- `tone_linkedin` (TEXT)
- `tone_blog` (TEXT)
- `tone_email` (TEXT)
- `core_principles` (JSON array)
- `phrases_to_use` (JSON array)
- `phrases_to_avoid` (JSON array)
- `vocabulary_level` (TEXT)

No schema changes required.

## API Endpoints

Already exist:
- `GET /api/brand-voice/config` - Get configuration
- `PUT /api/brand-voice/config` - Update configuration
- `DELETE /api/brand-voice/config` - Reset to defaults

No API changes required.

## Files to Modify

| File | Change |
|------|--------|
| `app/services/brand_voice_analyzer.py` | Add `get_brand_voice_config_context()` |
| `app/services/drafting.py` | Update `get_user_context()` to accept content_type, call new function |
| `frontend/settings.html` | Redesign Brand Voice tab with config form |

## Testing Strategy

1. Unit test `get_brand_voice_config_context()` returns correct format
2. Integration test that drafting includes brand voice config in prompts
3. E2E test: save config via UI, generate content, verify voice applied

## Rollout

1. Deploy backend changes (backward compatible - returns empty string if no config)
2. Deploy frontend changes
3. Monitor for errors in brand voice injection
