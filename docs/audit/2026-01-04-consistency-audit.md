# Code Consistency Audit Report

**Date:** 2026-01-04
**Auditor:** Claude Consistency Audit Skill
**Codebase:** Still (Content Multiplier)

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Total Python files | 87 |
| Total JavaScript files | 12 |
| Total HTML files | 29 |
| **Critical issues** | 0 |
| **Medium issues** | 3 |
| **Low priority issues** | 5 |

**Overall Health: GOOD** - The codebase demonstrates strong consistency across most patterns. Issues found are minor and don't pose security or reliability risks.

---

## Findings by Category

### 1. Duplicate Code

**Status: Minor Issues**

| Finding | Severity | Files |
|---------|----------|-------|
| `get_file_type()` duplicated | Medium | `app/api/upload.py:50`, `app/api/batch.py:39` |
| `get_setting()` helper duplicated | Low | `app/services/still_matcher.py:14`, `app/services/refresh_tasks.py:23` |

**Details:**
- `get_file_type()` appears in both `upload.py` (accepts filename + content_type) and `batch.py` (accepts only filename). These should be consolidated into a shared utility.
- `get_setting()` is a thin wrapper around `get_global_setting()` - defined separately in two services.

**Recommendation:** Create `app/utils/file_utils.py` for shared file handling functions.

---

### 2. Naming Conventions

**Status: Excellent**

| Pattern | Adherence |
|---------|-----------|
| Python snake_case | 100% |
| File naming (snake_case) | 100% |
| Frontend HTML (kebab-case) | 100% |
| Boolean prefixes (`is_`, `has_`) | Consistent |
| Async function prefixes | 99% use `get_`, 2 use `fetch_` (semantically correct for external calls) |
| Error variable naming | 97% use `e` |

**No action required.**

---

### 3. Error Handling

**Status: Good with Minor Issues**

| Pattern | Count |
|---------|-------|
| Try/catch blocks | 109 |
| `except Exception` (generic) | 57 (52%) |
| `except ValueError` (specific) | 23 (21%) |
| Silent catch blocks | 2 (acceptable - using `continue`) |

| Logging Method | Count |
|----------------|-------|
| `logger.*` | 91 |
| `logging.*` | 28 |
| `print()` | 22 |

**Issues:**
- 22 `print()` statements found, mostly in startup code (`app/database.py`, `app/main.py`)
- Generic `Exception` catching is high (52%) but acceptable for this type of application

**Recommendation (Low Priority):** Convert startup `print()` statements to `logger.info()` for consistency.

---

### 4. Import Organization

**Status: Excellent**

| Pattern | Adherence |
|---------|-----------|
| Absolute imports (`from app.x`) | 100% (241 occurrences) |
| Relative imports (`from .x`) | 0% |
| Import style (`from x import y`) | Consistent |
| Import ordering | Generally follows: stdlib → third-party → local |

**No action required.**

---

### 5. Architecture Patterns

**Status: Good with Structural Notes**

| Metric | Count |
|--------|-------|
| API routers | 22 |
| DB access in API layer | 360 calls |
| DB access in Services layer | 298 calls |
| Pydantic models in `app/models/` | 46 |
| Pydantic models inline in `app/api/` | 51 |

**Observations:**
- Database access is split between API and Services layers (not a clean separation)
- Some Pydantic models defined inline in API files rather than in `app/models/`
- All routers use consistent `router = APIRouter()` pattern

**Recommendation (Long-term):**
- Consider consolidating all Pydantic models into `app/models/`
- Consider moving DB operations to a repository/data access layer

---

### 6. Security Patterns

**Status: Good**

| Check | Result |
|-------|--------|
| Hardcoded secrets | None found |
| Auth on endpoints | All API files use `Depends(get_current_user_id)` or `Depends(verify_admin)` |
| SQL parameterization | 198 parameterized queries |
| f-string queries | 10 found - all use safe placeholder patterns |
| XSS prevention | `escapeHtml()` used consistently in frontend |
| Input validation | 148 validation/sanitization calls |

**No critical security issues found.**

---

### 7. Testing Patterns

**Status: Good**

| Test Type | Files | Tests |
|-----------|-------|-------|
| Python unit/integration | 7 | 82+ |
| E2E (Playwright) | 11 | Multiple |

**Test Files:**
- `tests/test_api.py` (14 tests)
- `tests/test_database.py` (7 tests)
- `tests/test_e2e.py` (16 tests)
- `tests/test_lifecycle.py` (13 tests)
- `tests/test_services.py` (25 tests)
- `tests/test_still_matcher.py` (4 tests)
- `tests/test_refresh_tasks.py` (3 tests)

**Patterns:**
- Shared fixtures in `conftest.py`
- Consistent `@pytest.mark.asyncio` usage
- Manual test checklist available

---

## Action Items

### Immediate (Fix This Week)
None - no critical issues found.

### Short-term (Technical Debt)

| Priority | Issue | Action | Files |
|----------|-------|--------|-------|
| Medium | Duplicate `get_file_type()` | Consolidate to shared utility | `app/api/upload.py`, `app/api/batch.py` |
| Low | Duplicate `get_setting()` helpers | Consider removing wrappers | `app/services/still_matcher.py`, `app/services/refresh_tasks.py` |
| Low | `print()` in startup code | Convert to logger | `app/database.py`, `app/main.py` |

### Long-term (Architectural Improvements)

| Priority | Issue | Action |
|----------|-------|--------|
| Low | Pydantic models scattered | Consolidate to `app/models/` |
| Low | DB access in API layer | Consider repository pattern |

---

## Recommended Standards

### Naming Conventions
- Python: snake_case for functions, variables, files
- Classes: PascalCase
- Boolean functions: `is_`, `has_`, `can_` prefix
- Async data retrieval: `get_` for internal, `fetch_` for external

### Error Handling
- Use `except Exception as e:` for generic catches
- Always log before re-raising or returning error
- Use `logger.*` not `print()`

### Imports
- Always use absolute imports (`from app.x import y`)
- Order: stdlib → third-party → local
- No wildcard imports

### Security
- All endpoints must use auth dependencies
- User-facing text: always use `escapeHtml()`
- SQL: always use parameterized queries

---

## Metrics Trend

This is the first audit. Future audits should track:
- [ ] Duplicate code count
- [ ] Test count and coverage
- [ ] Generic exception catch percentage
- [ ] Print statement count

---

## Next Steps

1. Address medium-priority duplicate code issue
2. Run this audit monthly to track consistency trends
3. Consider adding ESLint/Prettier for frontend JS (currently none configured)

---

*Generated by Claude Code Consistency Audit Skill*
