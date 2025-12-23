# ContentMultiplier

## Overview

ContentMultiplier is an AI-powered content repurposing platform that transforms long-form content (webinars, podcasts, PDFs) into multi-channel marketing campaigns. The application uses a 4-step quality pipeline (Atomize → Draft → Edit → Fact-check) to generate LinkedIn posts, blog posts, and emails from source material while maintaining brand voice and targeting specific audience personas.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Python FastAPI for async API handling
- **Database**: SQLite with aiosqlite for async operations (file-based at `database/contentmultiplier.db`)
- **Authentication**: JWT-based auth with bcrypt password hashing, 7-day token expiration
- **Rate Limiting**: slowapi for request throttling by user ID or IP address

### AI Model Integration
The system uses three AI providers in a specific pipeline:
1. **Gemini 2.0 Flash** (Google): Transcription, atomization, editing, and scoring
2. **Claude Opus 4.5** (Anthropic): Content drafting with brand voice preservation
3. **Gemini 2.5 Flash** (Google): Fact-checking

OpenRouter support is available as an alternative to direct Anthropic API access.

### Admin Settings
- **Settings Page** (`/admin/settings`): Configure API keys and model selection
- **Model Selection**: Admin can select specific models for each pipeline step (transcription, atomization, drafting, editing, fact-checking)
- **OpenRouter Dynamic Models**: Drafting model dropdown dynamically loads all available models from OpenRouter when API key is configured
- **Model Refresh**: Users can click the Refresh button to reload available OpenRouter models
- **API Key Management**: Keys entered in admin UI are session-only; use Replit Secrets for persistence
- **Settings Storage**: Model configuration persists in `data/settings.json`

### Content Processing Pipeline
1. **Transcription**: Convert audio/video/PDF to text using Gemini
2. **Atomization**: Extract reusable content atoms (data, insights, stories, problems, solutions)
3. **Drafting**: Generate content pieces using Claude with persona-specific prompts
4. **Editing**: Refine for target audience using Gemini
5. **Fact-checking**: Verify claims against source material

### Frontend Architecture
- **Technology**: Vanilla JavaScript with Tailwind CSS (CDN-loaded)
- **Authentication**: Token-based with localStorage persistence
- **Admin Panel**: Jinja2 templates served from `/app/templates/admin/`

### Data Organization
- `data/prompts/`: Text-based prompt templates with variable substitution
- `data/clients/`: Client-specific configuration storage
- `data/jobs/`: Uploaded file storage organized by job ID
- `data/personas.json`: Target audience persona definitions

### Key Design Patterns
- **Prompt Template System**: Text files with `{variable}` placeholders, rendered at runtime
- **Circuit Breaker Pattern**: Retry logic with exponential backoff for AI API calls
- **Background Processing**: Long-running jobs execute asynchronously with progress tracking
- **Content Library**: Extracted atoms stored for reuse across multiple content generations

## External Dependencies

### AI APIs (Required)
- **Google AI Studio** (Gemini): Primary transcription and processing - requires `GEMINI_API_KEY`
- **Anthropic** (Claude): Content drafting - requires `ANTHROPIC_API_KEY`
- **OpenRouter** (Optional): Alternative to Anthropic - requires `OPENROUTER_API_KEY`

### Python Packages
- `google-generativeai`: Gemini API client
- `anthropic`: Claude API client
- `aiosqlite`: Async SQLite database access
- `python-jose`: JWT token handling
- `passlib`: Password hashing with bcrypt
- `slowapi`: Rate limiting middleware

### File Storage
- Local filesystem for uploads (configurable via `upload_dir`)
- Maximum upload size: 100MB (configurable)
- Supported formats: MP4, MOV, AVI, WebM, MP3, WAV, M4A, PDF, TXT, MD

### Environment Variables
```
GEMINI_API_KEY=         # Required for transcription/processing
ANTHROPIC_API_KEY=      # Required for drafting (unless using OpenRouter)
OPENROUTER_API_KEY=     # Optional alternative to Anthropic
SECRET_KEY=             # JWT signing key (change in production)
```