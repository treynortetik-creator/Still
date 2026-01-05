# Brand Company Information Feature Design

## Overview

Add a "Company Knowledge Base" text field to the user settings that allows users to provide comprehensive information about their brand/company. This information becomes available as a prompt variable `{brand_company_info}` in the Admin Panel prompt editor.

## User Story

As a user, I want to provide information about my company's products, services, FAQs, competitor differentiators, and commonly used facts so that the AI can reference this knowledge when generating content.

## Design

### 1. Database Changes

**Table:** `brand_voice_config` (existing)

**New Column:**
```sql
ALTER TABLE brand_voice_config ADD COLUMN IF NOT EXISTS company_info TEXT;
```

### 2. Backend API Changes

**File:** `app/api/brand_voice.py`

Add `company_info` to the `BrandVoiceConfig` Pydantic model:
```python
company_info: Optional[str] = None
```

**File:** `app/api/admin.py`

Add to the "Brand Voice Variables" category in `get_prompt_variables()`:
```python
{
    "name": "brand_company_info",
    "description": "Company knowledge base - products, services, FAQs, differentiators, facts"
}
```

**File:** `app/services/drafting.py`

When building variables dict for prompt rendering:
```python
variables["brand_company_info"] = brand_config.get("company_info", "") or ""
```

### 3. Frontend UI Changes

**File:** `frontend/settings.html`

**Tab Rename:**
- Change "Brand Voice" tab button text to "Brand Information"

**New Section:**
Add "Company Knowledge Base" section at the top of the Brand Information tab:

- Section header: "Company Knowledge Base"
- Helper text: "Information about your company that AI can reference when creating content."
- Large textarea (~8-10 rows)
- Placeholder text with examples:
  - Products and services
  - Key differentiators from competitors
  - Commonly cited facts and statistics
  - FAQs and standard responses
  - Company history and milestones

### 4. Files to Modify

| File | Changes |
|------|---------|
| `app/api/brand_voice.py` | Add `company_info` to Pydantic model |
| `app/api/admin.py` | Add `brand_company_info` to prompt variables list |
| `app/services/drafting.py` | Include variable in prompt rendering |
| `frontend/settings.html` | Rename tab, add textarea section |
| Database migration | Add `company_info` column |

### 5. Variable Usage

After implementation, admins can use `{brand_company_info}` in any prompt template via the Admin Panel prompt editor. The variable will be replaced with the user's company information when generating content.
