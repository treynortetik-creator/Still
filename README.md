# ContentMultiplier MVP

AI-powered content repurposing platform that transforms long-form content (webinars, podcasts, PDFs) into multi-channel marketing campaigns.

## Key Features

- **4-Step Quality Pipeline**: Atomize → Draft → Edit → Fact-check
- **Content Library**: Reusable atoms (quotes, stats, insights) that grow with each upload
- **Persona-Driven**: Tailor content to target audience priorities
- **Universal Inputs**: Video, audio, PDF, text
- **Quality Scoring**: Rank outputs by Hook, Brand Alignment, Clarity, Engagement
- **Brand Voice Preview**: Test persona transformations before processing
- **Magic Words**: Domain vocabulary for accurate transcription

## Tech Stack

- **Backend**: Python FastAPI + SQLite
- **AI Models**:
  - Gemini 2.0 Flash (transcription, atomization, editing)
  - Claude Opus 4.5 (drafting with brand voice)
  - Gemini 2.5 Flash (fact-checking, scoring)
- **Frontend**: Vanilla JavaScript + Tailwind CSS
- **Deployment**: Replit (MVP), Railway/Render (production)

---

## Quick Start

### Prerequisites

- Python 3.13+
- API keys:
  - Anthropic (Claude) - [console.anthropic.com](https://console.anthropic.com/)
  - Google AI Studio (Gemini) - [aistudio.google.com](https://aistudio.google.com/)

### Installation

1. **Clone repository**
   ```bash
   git clone [repo-url]
   cd contentmultiplier
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file**
   ```bash
   cp .env.example .env
   ```

4. **Add your API keys to `.env`**:
   ```bash
   ANTHROPIC_API_KEY=your_claude_key_here
   GEMINI_API_KEY=your_gemini_key_here
   SECRET_KEY=your_secret_key_here
   ```

5. **Run the application**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

6. **Access the app**
   - Main app: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - Admin panel: http://localhost:8000/admin/dashboard

---

## First-Time Setup

### 1. Register an Account
- Go to http://localhost:8000/register.html
- Create account with email and password

### 2. Default Personas
Personas are pre-configured:
- **CEO of Long-Term Care Facility** - ROI-focused, executive level
- **Director of Nursing (Memory Care)** - Clinical, care-quality focused
- **Marketing Director (Senior Living)** - Brand and positioning focused

### 3. Test with Sample Content
1. Go to `/upload.html`
2. Select or paste sample content
3. Choose target persona
4. Enter magic words (optional): "YourBrand, Q4, ROI"
5. Select assets: 3 LinkedIn posts, 1 blog
6. Click "Upload & Process"
7. Watch status page for 10-15 minutes
8. View results and quality scores

---

## Project Structure

```
contentmultiplier/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration settings
│   ├── database.py             # SQLite database setup
│   ├── api/                    # API endpoints
│   │   ├── auth.py             # Authentication (register, login)
│   │   ├── upload.py           # File upload
│   │   ├── jobs.py             # Job management
│   │   ├── library.py          # Content library
│   │   ├── personas.py         # Persona & brand voice preview
│   │   └── admin.py            # Admin endpoints
│   ├── services/               # Business logic
│   │   ├── transcription.py    # Gemini transcription
│   │   ├── atomization.py      # Content atomization
│   │   ├── drafting.py         # Content drafting (Claude)
│   │   ├── editing.py          # Audience editing
│   │   ├── factcheck.py        # Fact-checking
│   │   ├── scoring.py          # Quality scoring
│   │   └── pipeline.py         # Orchestrator
│   ├── models/                 # Pydantic models
│   ├── utils/                  # Utilities
│   │   ├── retry.py            # Retry logic
│   │   └── error_messages.py   # Enhanced error handling
│   └── templates/admin/        # Admin UI templates
├── data/
│   ├── prompts/                # Editable prompt templates
│   ├── clients/                # Client brand contexts
│   └── database/               # SQLite database
├── frontend/                   # User-facing UI
│   ├── index.html              # Landing page
│   ├── login.html              # Login
│   ├── register.html           # Registration
│   ├── upload.html             # Upload interface
│   ├── status.html             # Job status
│   ├── results.html            # Results display
│   ├── library.html            # Content library
│   ├── settings.html           # Settings & brand voice testing
│   └── static/                 # CSS, JS assets
├── tests/                      # Test suite
│   ├── test_e2e.py             # End-to-end tests
│   └── MANUAL_TEST_CHECKLIST.md
├── docs/                       # Documentation
│   └── BETA_ONBOARDING.md      # Beta user guide
└── scripts/                    # Utility scripts
```

---

## Usage Guide

### For Users

**Upload Content**:
1. Log in at `/login.html`
2. Go to Upload page
3. Upload video/audio/PDF or paste text
4. Select target persona
5. Choose output types (LinkedIn, Blog)
6. Add "magic words" for transcription accuracy (optional)
7. Click "Upload & Process"

**View Results**:
- See quality scores (0-100) for each output
- Hover over scores for breakdown (Hook, Brand, Clarity, Engagement)
- Copy or download content
- View extracted atoms

**Use Content Library**:
- Browse saved atoms from all uploads
- Filter by type (data, insight, story, problem, solution)
- Select atoms and generate new content without uploading

**Test Brand Voice**:
- Go to Settings page
- Enter sample text
- Select persona
- See side-by-side transformation preview

### For Admins

**Edit Prompts**:
1. Go to `/admin/prompts`
2. Click "Edit" on any template
3. Modify prompt text
4. Save - changes apply to all new jobs

**Monitor Usage**:
- View job counts at `/admin/dashboard`
- Track API costs
- Review recent jobs

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload content |
| GET | `/api/job/{job_id}/status` | Get job status |
| GET | `/api/job/{job_id}/results` | Get results |

### Library
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/library` | Browse library |
| POST | `/api/generate-from-library` | Generate from atoms |

### Personas
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/personas` | List personas |
| POST | `/api/personas/preview-voice` | Preview brand voice |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/dashboard` | Admin dashboard |
| GET | `/admin/prompts` | List prompts |
| PUT | `/admin/prompts/{name}` | Update prompt |

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | Yes |
| `SECRET_KEY` | JWT signing key | Yes |
| `DATABASE_URL` | SQLite database path | No (default: ./database/) |
| `UPLOAD_MAX_SIZE_MB` | Max upload size | No (default: 500) |
| `ENVIRONMENT` | development/production | No (default: development) |

### Prompt Templates

Edit in `/data/prompts/` or via admin UI:
- `atomization.txt` - Content extraction
- `linkedin_draft.txt` - LinkedIn post generation
- `blog_draft.txt` - Blog article generation
- `audience_edit.txt` - Audience optimization
- `factcheck.txt` - Fact-checking

---

## Cost Structure

**Per job (typical 1-hour video)**:
| Step | Model | Cost |
|------|-------|------|
| Transcription | Gemini 2.0 Flash | ~$0.05 |
| Atomization | Gemini 2.0 Flash | ~$0.10 |
| Drafting | Claude Opus 4.5 | ~$2.00 |
| Editing | Gemini 2.0 Flash | ~$0.05 |
| Fact-checking | Gemini 2.5 Flash | ~$0.01 |
| Scoring | Gemini 2.0 Flash | ~$0.02 |
| **Total** | | **~$2.23** |

---

## Testing

### Automated Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/test_e2e.py -v --asyncio-mode=auto

# Run specific test class
pytest tests/test_e2e.py::TestUserJourney -v
```

### Manual Testing
Follow the checklist in `tests/MANUAL_TEST_CHECKLIST.md`

---

## Deployment

### Replit (MVP)

1. Import repository to Replit
2. Set environment secrets in Replit
3. Click "Run"

See `.replit` and `replit.nix` for configuration.

### Production (Railway/Render)

1. Connect GitHub repository
2. Set environment variables
3. Deploy

---

## Troubleshooting

**Jobs fail during transcription**:
- Check API keys in `.env`
- Verify file is <500MB
- Check file format is supported (MP4, MP3, PDF, TXT)

**Outputs seem generic**:
- Review persona selection
- Edit prompt templates in admin
- Add magic words for domain vocabulary

**Rate limit errors**:
- Default: 10 uploads/hour/user
- Wait or adjust in `app/main.py`

**Login issues**:
- Clear browser storage
- Check token expiration (24 hours)

---

## Development

### Running Locally
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Adding New Personas
Edit `app/services/persona_manager.py` → `get_default_personas()`

### Adding New Asset Types
1. Create prompt template in `/data/prompts/`
2. Add drafting function in `app/services/drafting.py`
3. Update pipeline in `app/services/pipeline.py`
4. Add UI elements in frontend

---

## License

Proprietary - All rights reserved

## Support

For issues: treynor@contentmultiplier.com
