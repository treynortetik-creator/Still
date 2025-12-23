# ContentMultiplier MVP

AI-powered content repurposing platform that transforms long-form content (webinars, podcasts, PDFs) into multi-channel marketing campaigns.

## Features

- **4-Step AI Pipeline**: Atomize → Draft → Edit → Fact-check
- **Content Library**: Extracts and saves reusable "atoms" (quotes, stats, stories) from every upload
- **Multi-Channel Output**: Generate LinkedIn posts, blog articles, and emails
- **Persona-Targeted**: Content optimized for specific target audiences
- **Admin Interface**: Edit prompts, manage clients, monitor costs

## Tech Stack

- **Backend**: Python FastAPI with async processing
- **Database**: SQLite
- **AI Models**:
  - Gemini 2.0 Flash: Transcription, cleanup, atomization, editing
  - Claude Opus 4.5: Drafting (brand voice alignment)
  - Gemini 2.5 Flash: Fact-checking
- **Frontend**: Vanilla JavaScript + Tailwind CSS

## Quick Start

1. **Clone and install dependencies**:
   ```bash
   cd contentmultiplier
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the application**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

4. **Open in browser**:
   - Main app: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - Admin panel: http://localhost:8000/admin/dashboard

## Project Structure

```
contentmultiplier/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database setup
│   ├── api/                  # API endpoints
│   │   ├── upload.py        # File upload
│   │   ├── jobs.py          # Job management
│   │   ├── library.py       # Content library
│   │   └── admin.py         # Admin endpoints
│   ├── services/            # Business logic
│   │   ├── transcription.py # Gemini transcription
│   │   ├── atomization.py   # Content atomization
│   │   ├── drafting.py      # Content drafting
│   │   ├── editing.py       # Audience editing
│   │   ├── factcheck.py     # Fact-checking
│   │   └── pipeline.py      # Orchestrator
│   ├── models/              # Pydantic models
│   └── templates/           # Jinja2 templates
├── data/
│   ├── prompts/             # Editable prompt templates
│   ├── clients/             # Client brand contexts
│   └── jobs/                # Uploaded files
├── frontend/                # Static frontend files
├── database/                # SQLite database
└── tests/                   # Test suite
```

## API Endpoints

### User-Facing

- `POST /api/upload` - Upload file for processing
- `POST /api/upload-text` - Upload text content
- `GET /api/job/{job_id}/status` - Get job status
- `GET /api/job/{job_id}/results` - Get job results
- `GET /api/library` - Browse content library
- `POST /api/generate-from-library` - Generate from library atoms

### Admin

- `GET /admin/dashboard` - Dashboard view
- `GET /admin/prompts` - List prompt templates
- `PUT /admin/prompts/{name}` - Update prompt
- `GET /admin/clients` - List clients
- `GET /admin/costs` - Cost breakdown

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `DATABASE_URL` | SQLite database path |
| `UPLOAD_MAX_SIZE_MB` | Max upload size (default: 100) |

### Prompt Templates

Edit prompts in `/data/prompts/` or through the admin UI:
- `atomization.txt` - Content extraction
- `linkedin_draft.txt` - LinkedIn post generation
- `blog_draft.txt` - Blog article generation
- `email_draft.txt` - Email generation
- `audience_edit.txt` - Audience optimization
- `factcheck.txt` - Fact-checking

## Testing

```bash
pytest tests/ -v
```

## Development

### Running in Development Mode

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Adding New Personas

Edit `/data/personas.json` to add new target personas.

### Adding New Asset Types

1. Create prompt template in `/data/prompts/`
2. Add drafting function in `app/services/drafting.py`
3. Update pipeline in `app/services/pipeline.py`
4. Add UI elements in frontend

## License

Proprietary - All rights reserved
