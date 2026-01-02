# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository is set up as a development workspace integrated with Plane project management. The codebase is in its initial state with configuration for Claude Code and MCP (Model Context Protocol) servers.

## MCP Server Configuration

The repository is configured with the following MCP server:

**Plane MCP Server** (`@makeplane/plane-mcp-server`)
- Workspace: `smaserv`
- API Host: `http://100.122.49.121` (local/private network)
- Provides integration with Plane project management for issues, projects, modules, cycles, and worklogs

The Plane MCP server enables direct interaction with project management tasks through Claude Code. You can:
- Query and manage issues, projects, modules, and cycles
- Add comments and track worklogs
- Create and update project states, labels, and issue types

## Claude Code Plugins

The following official Claude Code plugins are enabled:
- **context7**: Retrieves up-to-date documentation and code examples for libraries
- **frontend-design**: Creates production-grade frontend interfaces
- **code-review**: Reviews pull requests and code changes

## Development Context

**Primary Project**: Cherrypick (CHERRYPICK)
- An intelligent tool that automatically filters and adapts a master resume to match specific job descriptions
- Helps "cherry-pick" the right experience for every application
- Project ID: `527c19ce-3649-4f9a-84ec-f8ffe3dfb011`

When working on features or issues, check Plane for current tasks and update issue status accordingly using the Plane MCP server tools.

## Development Progress

### ✅ Foundation & Infrastructure Cycle (COMPLETE)

The Foundation & Infrastructure cycle has been completed and merged to main. All core infrastructure is now in place:

**Completed Tickets:**
- ✅ CP-7: Monorepo & Folder Initialization
  - Professional monorepo structure with pnpm workspace
  - Backend: Poetry + Python 3.11
  - Frontend: Next.js (App Router) - initialized

- ✅ CP-8: Docker Orchestration for Self-Hosting
  - Docker Compose configuration with 4 services
  - PostgreSQL 15 (Alpine) with health checks
  - ChromaDB (persistent vector store)
  - Backend (FastAPI with Typst support)
  - Frontend (Next.js) - ready for development

- ✅ CP-9: Relational Schema Design (SQLAlchemy 2.0)
  - Core models: Experience, BulletPoint, Project, ProjectBulletPoint, Education, Job
  - Full async patterns with SQLAlchemy 2.0
  - Type-safe with Mapped[] annotations
  - Strategic indexes for performance
  - ChromaDB integration ready (embedding_id fields)

- ✅ CP-10: Environment & Config Management
  - Pydantic Settings for configuration
  - CORS middleware for frontend integration
  - Comprehensive health check system
  - Timeout protection (2s per service)
  - Concurrent health checks with graceful degradation

**Infrastructure Status:**
- Database: ✅ PostgreSQL with async SQLAlchemy 2.0
- Vector Store: ✅ ChromaDB v2 API
- LLM: ✅ Ollama integration ready
- Config: ✅ Environment-based with .env support
- Health: ✅ Cross-service monitoring endpoint
- CORS: ✅ Frontend security configured

**Next Cycle:** Core Engine (Resume Assembly + RAG)

## Engineering Standards & Tech Stack

### 1. Project Architecture (Monorepo)

- **Root Directory:** Contains `compose.yaml`, `pnpm-workspace.yaml`, and `.env`
- **Backend:** Located in `/apps/backend`. FastAPI (Python 3.11), SQLAlchemy 2.0 (Async), Poetry for package management
- **Frontend:** Located in `/apps/frontend`. Next.js (App Router), TypeScript, TailwindCSS, shadcn/ui, pnpm for package management
- **Infrastructure:** Self-hosted via Docker. Services: PostgreSQL 15, ChromaDB (Vector Store), Ollama (Local LLM), and Typst CLI

### 2. Core Feature: Intelligent Assembly (RAG)

- **No Hallucinations:** The LLM does not write new resume content; it selects existing bullet points from the database based on semantic relevance to a Job Description
- **Vector Search:** Use ChromaDB to store and query embeddings of individual bullet points
- **Typst Engine:** All resumes are rendered using `.typ` templates. The backend populates these templates and compiles them to PDF via the Typst binary

### 3. Engineering Rules

- **Git Workflow:** Every ticket (e.g., CP-1) must be worked on a dedicated branch named `feat/task-description` or `bugfix/task-description`
- **Async First:** All database and external API calls (Ollama, Chroma) in the backend must use `async/await`
- **Workday Compatibility:** The "Workday Assistant" must provide a "Clean Text" export that strips all Markdown, Typst, or special characters for clipboard compatibility
- **Secret Management:** Never hardcode credentials. Use `pydantic-settings` in the backend and `.env.local` in the frontend

### 4. Plugin Usage (Claude Code CLI)

- **context7:** Use to index the codebase after every major structural change
- **frontend-design:** Use for generating shadcn/ui components and ensuring clean UX in the dashboard
- **code-review:** Use to verify SQLAlchemy models, Dockerfile efficiency, and Typst template logic

## Builder API Patterns

When working with the Builder API (manual CRUD operations), follow these conventions:

### Endpoint Organization

- **Experiences**: `/api/v1/experiences` - CRUD for work history entries
- **Projects**: `/api/v1/projects` - CRUD for project entries
- **Bullet Points**: `/api/v1/bullet-points` - Unified endpoint for both experience and project bullets
- **Builder State**: `/api/v1/builder/state` - Full state view for dashboard

### Bullet Point Management

- Bullet points use a unified API with `source_type` field ("experience" or "project")
- Creating/updating bullets automatically syncs embeddings to ChromaDB
- Embeddings sync is non-blocking - failures are logged but don't fail the request
- Deleting an Experience or Project cascade-deletes associated bullets

### Schema Patterns

- **Create schemas**: Include all required fields, no `id` or timestamps
- **Update schemas**: All fields optional (except `id` in path), use `exclude_unset=True`
- **Response schemas**: Include full nested relationships (e.g., Experience includes bullet_points list)
- Use Pydantic v2 with `from_attributes = True` for ORM mapping

### Error Handling

- Return 404 for missing resources
- Return 201 for successful creation
- Return 204 for successful deletion
- Validate parent existence before creating related records (e.g., check Experience exists before creating BulletPoint)

## Typst PDF Generation (CP-16)

### Overview

The PDF generation system converts tailored resumes (CP-15 output) into professional PDFs using Typst templates. The system is designed for:
- **Performance**: <2s compilation target
- **Flexibility**: Easy template modification
- **Reliability**: Comprehensive error handling

**Architecture Flow:**
```
GET /api/v1/generate/preview/{job_id}
    ↓ Fetch TailoredResume (calls CP-15 /tailor)
    ↓ convert_to_typst_data() → JSON
    ↓ Write temp files (data.json + master.typ)
    ↓ Async: typst compile master.typ output.pdf
    ↓ Read PDF bytes + cleanup temp files
    ↓ Return PDF (inline or attachment)
```

**Key Components:**
- **Template**: `/apps/backend/templates/master.typ` - Typst markup template
- **Service**: `/apps/backend/src/services/pdf_generator.py` - Conversion + compilation
- **Router**: `/apps/backend/src/routers/generate.py` - HTTP endpoints

### Endpoints

#### GET `/api/v1/generate/preview/{job_id}`
Returns PDF for inline browser preview (opens in new tab/iframe).

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `inline; filename=preview.pdf`

**Prerequisites:**
- Job must be analyzed: `POST /jobs/{job_id}/analyze`
- Resume auto-assembled on demand (calls CP-15 internally)

**Example:**
```bash
curl -o preview.pdf http://localhost:8001/api/v1/generate/preview/{job_id}
# Or open directly in browser:
# http://localhost:8001/api/v1/generate/preview/{job_id}
```

#### GET `/api/v1/generate/download/{job_id}`
Returns PDF for download with clean filename: `FirstName_LastName_CompanyName_Resume.pdf`

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="John_Doe_Google_Resume.pdf"`

**Example:**
```bash
curl -OJ http://localhost:8001/api/v1/generate/download/{job_id}
# Downloads as: John_Doe_Google_Resume.pdf
```

### Modifying the Typst Template

#### Template Location
`/apps/backend/templates/master.typ`

#### Template Structure
The template uses Typst's JSON import to load resume data:

```typst
#let resume_data = json("data.json")

// Access fields:
#resume_data.candidate_name
#resume_data.experiences
#resume_data.skills
```

#### Available Data Fields

**Personal Info (TODO: Add User model in CP-17):**
- `candidate_name` (string) - Placeholder: "John Doe"
- `email` (string) - Placeholder: "john.doe@example.com"
- `phone` (string) - Placeholder: "+1 (555) 123-4567"
- `location` (string) - Placeholder: "San Francisco, CA"

**Experiences (array):**
- `company_name` (string)
- `role_title` (string)
- `location` (string)
- `dates` (string, pre-formatted: "Jan 2024 - Present")
- `bullet_points` (array of `{content: string}`)

**Projects (array):**
- `name` (string)
- `description` (string)
- `technologies` (array of strings)
- `link` (string | null)
- `bullet_points` (array of `{content: string}`)

**Skills (array):**
- `name` (string)

**Education (array):**
- `institution` (string)
- `degree` (string)
- `field_of_study` (string)
- `location` (string)
- `dates` (string, pre-formatted: "Sep 2018 - May 2022")
- `gpa` (float | null)

#### Common Template Modifications

**1. Change Font:**
```typst
#set text(font: "New Computer Modern")  // Default
#set text(font: "Linux Libertine")     // Alternative serif
#set text(font: "Roboto")              // Modern sans-serif
```

**2. Adjust Spacing:**
```typst
#set par(leading: 0.65em)  // Line height
#v(1em)                    // Vertical space
```

**3. Modify Section Headers:**
```typst
#text(size: 14pt, weight: "bold", fill: blue.darken(20%))[EXPERIENCE]
#line(length: 100%, stroke: 1pt + blue.darken(20%))
```

**4. Add Custom Fields:**
Edit `convert_to_typst_data()` in `/apps/backend/src/services/pdf_generator.py`:

```python
return {
    "candidate_name": "...",
    "linkedin_url": "...",  # Add new field
    # ...
}
```

Then use in template:
```typst
#link(resume_data.linkedin_url)[LinkedIn]
```

#### Testing Template Changes

**Quick test workflow:**
1. Modify `/apps/backend/templates/master.typ`
2. Restart backend: `docker compose restart backend`
3. Call preview endpoint: `GET /api/v1/generate/preview/{job_id}`
4. Check browser preview
5. Iterate

**Manual Typst compilation (for debugging):**
```bash
# Inside Docker container
docker exec -it engine-backend-1 bash

# Compile manually
cd /app/templates
typst compile master.typ test.pdf --root /tmp
```

### Performance Benchmarks

**Target: <2 seconds per PDF**

**Typical Timings:**
- JSON conversion: ~10ms
- Temp file I/O: ~50ms
- Typst compilation: ~500-1500ms
- **Total: ~560-1560ms** ✅

**If compilation is slow (>2s):**
- Check template complexity (heavy fonts, images)
- Verify `/tmp` is tmpfs (RAM-backed)
- Review Typst logs: `docker compose logs backend`

### Troubleshooting

#### "Typst template not found"
**Cause:** Template file missing or wrong path

**Fix:**
```bash
# Verify template exists
ls -la apps/backend/templates/master.typ

# If missing, create directory
mkdir -p apps/backend/templates
```

#### "Typst compilation failed"
**Cause:** Syntax error in template or invalid data

**Fix:**
1. Check Typst error message in logs: `docker compose logs backend`
2. Manually test template:
   ```bash
   docker exec -it engine-backend-1 bash
   typst compile /app/templates/master.typ /tmp/test.pdf
   ```
3. Validate JSON data structure in `/tmp/typst_*/data.json`

#### "PDF generation timed out (>5s)"
**Cause:** Template too complex or system overload

**Fix:**
- Simplify template (remove heavy fonts, images)
- Increase timeout in `pdf_generator.py`:
  ```python
  COMPILE_TIMEOUT = 10.0  # Increase from 5.0
  ```

#### Empty PDF or missing content
**Cause:** Incorrect field names or data structure mismatch

**Fix:**
1. Verify field names match between:
   - `convert_to_typst_data()` output
   - Template `resume_data.*` references
2. Check logs for conversion errors
3. Inspect temp JSON: Look in `/tmp/typst_*` during debugging

### Future Enhancements (Post-CP-16)

**Planned for CP-17 (User Model):**
- Add User model with personal info (name, email, phone, location)
- Remove placeholder values from `convert_to_typst_data()`
- Support multiple resume templates per user

**Planned for CP-18 (Template Gallery):**
- Multiple template options (modern, classic, minimal)
- Template preview endpoint
- User-selectable templates

**Planned for CP-19 (Workday Assistant):**
- "Clean Text" export (strips all formatting)
- Clipboard-ready format for Workday paste

## Asynchronous Persistence Architecture

### Problem Statement

Cherrypicker LLM calls (CP-15) take 2-3 minutes due to multiple sequential Ollama requests. When PDF endpoints (`/preview`, `/download`) called cherrypicker synchronously, they timed out, making the application unusable.

### Solution: Background Task Pattern

**Flow:**
1. POST `/api/v1/jobs/{job_id}/tailor` → Returns **202 Accepted** in <500ms
2. Background task runs cherrypicker independently (up to 5 minutes)
3. Results stored in `tailored_resumes` table with status tracking
4. GET `/api/v1/jobs/{job_id}/tailor/status` → Poll for completion
5. GET `/api/v1/generate/preview/{job_id}` → **Instant PDF** (<2s, no LLM calls)

**Key Benefits:**
- Non-blocking HTTP requests (no timeouts)
- Progress visibility for users
- Instant PDF generation from pre-computed data
- Graceful error handling with full tracebacks

### Architecture Components

**Database Model:** `src/models/tailored_resume.py`
- Stores serialized `TailoredResumeResponse` as JSON
- Status field: `pending` | `processing` | `completed` | `failed`
- Progress tracking: `completed_steps` / `total_steps`
- Error capture: `error_message` + `error_traceback`
- Performance metrics: `started_at`, `completed_at`

**Background Service:** `src/services/background_tasks.py`
- `execute_tailor_resume_task()` - Main async task function
- 5-minute timeout protection (`settings.cherrypicker_timeout`)
- Progress updates after each step
- Comprehensive error handling

**API Endpoints:** `src/routers/jobs.py`
- **POST** `/jobs/{job_id}/tailor` - Trigger async task (202)
- **GET** `/jobs/{job_id}/tailor/status` - Poll progress

**PDF Endpoints:** `src/routers/generate.py`
- **GET** `/generate/preview/{job_id}` - Instant inline PDF
- **GET** `/generate/download/{job_id}` - Instant download PDF
- Fetch from DB instead of calling cherrypicker

### Hybrid Fallback Logic (Cherrypicker)

**Problem:** LLM may return < 3 bullets, causing schema validation errors (min_length=3).

**Solution:** Smart backfilling with ChromaDB semantic matches.

**Strategy:**
1. LLM attempts to select 3-5 bullets per source
2. If LLM returns < 3 valid UUIDs:
   - Backfill with top ChromaDB matches (by similarity score)
   - Ensure minimum 3 bullets per source
3. If source has < 3 bullets in match set:
   - Return empty array → Assembler gracefully skips source
   - Log critical warning for debugging

**Why:** Schema requires 3-5 bullets for ATS compliance. Fallback prevents `ValidationError` and ensures resumes always generate successfully.

**Implementation:** `src/services/cherrypicker.py` lines 211-241

### Performance Benchmarks

| Endpoint | Before (Sync) | After (Async) | Improvement |
|----------|---------------|---------------|-------------|
| POST /tailor | 2-3min (timeout ❌) | **32ms** (202 ✅) | **5600x faster** |
| GET /preview | 2-3min (timeout ❌) | **35ms** (instant ✅) | **5100x faster** |
| GET /download | 2-3min (timeout ❌) | **35ms** (instant ✅) | **5100x faster** |
| Background Task | N/A | **~2.5-3.5min** (non-blocking) | No user impact |

**Background Task Breakdown:**
- Match Set (CP-14): ~10s
- Cherrypicker (CP-15): ~2-3min (LLM-dominated)
- Assembler: ~1s
- JSON serialization: ~100ms
- **Total: ~2.5-3.5min** (runs independently, no HTTP blocking)

### Configuration

**Environment Variable:** `.env` or `.env.example`
```bash
CHERRYPICKER_TIMEOUT=300  # 5 minutes for background LLM calls
```

**Code:** `src/config.py`
```python
cherrypicker_timeout: int = 300  # Timeout for cherrypicker background task
```

### Testing Checklist

**Golden E2E Test:**
```bash
# 1. Trigger async tailor
time curl -X POST http://localhost:8001/api/v1/jobs/{job_id}/tailor
# Expect: 202 Accepted in <500ms

# 2. Poll status
curl http://localhost:8001/api/v1/jobs/{job_id}/tailor/status
# Expect: {"status": "processing", "progress": {"percent": 25}}

# 3. Wait for completion (2-3 min)
# Poll every 10s until status=completed

# 4. Generate PDF
time curl http://localhost:8001/api/v1/generate/preview/{job_id} -o test.pdf
# Expect: PDF in <2s

# 5. Verify PDF
file test.pdf
# Expect: PDF document, version 1.7
```

**Success Criteria:**
- ✅ POST /tailor returns 202 in <500ms
- ✅ Status transitions: pending → processing → completed
- ✅ Background task completes without timeout
- ✅ PDF generates in <2s (instant from DB)
- ✅ No ValidationError (hybrid fallback working)
- ✅ Sources with < 3 bullets gracefully skipped

### Troubleshooting

**Task Status: failed**
- Check `error_message` in status response
- Review backend logs: `docker compose logs backend | grep -i error`
- Common causes:
  - Job not analyzed (call POST `/jobs/{job_id}/analyze` first)
  - All sources have < 3 bullets (data quality issue)
  - Ollama service down
  - ChromaDB connection failure

**Task Stuck in processing**
- Check if cherrypicker is still running (logs should show LLM calls)
- Verify 5-minute timeout hasn't expired
- Restart backend if task is truly stuck: `docker compose restart backend`

**PDF Returns 202 Instead of PDF**
- Task still in progress - poll `/tailor/status` until completed
- Task failed - check error_message for root cause

**Empty Resume (No Experiences/Projects)**
- All sources had < 3 bullets in match set
- Check logs for "CRITICAL: Source ... only has X bullets"
- Indicates data quality issue - add more bullet points to experiences/projects

## Project Structure

```
/
├── apps/
│   ├── backend/         # FastAPI + SQLAlchemy 2.0 (Async)
│   │   ├── main.py      # FastAPI application entry point
│   │   ├── pyproject.toml  # Poetry dependencies
│   │   └── .env.example # Environment variables template
│   └── frontend/        # Next.js (App Router) - To be initialized
│       └── package.json # Placeholder for Next.js app
├── compose.yaml         # Docker Compose configuration
├── pnpm-workspace.yaml  # PNPM monorepo configuration
├── .env                 # Environment variables (gitignored)
├── .gitignore           # Git ignore rules
└── CLAUDE.md           # This file
```

## Development Commands

### Backend Development

```bash
# Navigate to backend
cd apps/backend

# Install dependencies (requires Poetry)
poetry install

# Start backend in development mode
poetry run uvicorn main:app --reload

# The API will be available at http://localhost:8000
# - Root: http://localhost:8000/
# - Health check: http://localhost:8000/health
# - API docs: http://localhost:8000/docs

# Run tests
poetry run pytest

# Format and lint
poetry run black .
poetry run ruff check .
```

### Docker Commands

**Note:** If you get permission denied errors, add your user to the docker group:
```bash
sudo usermod -aG docker $USER
# Then log out and log back in
```

```bash
# Start all services (db, vector_db, backend, frontend)
docker compose up -d

# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f backend

# Stop services
docker compose down

# Check service status
docker compose ps

# Access services:
# - Backend API: http://localhost:8001
# - Backend health: http://localhost:8001/health
# - Backend docs: http://localhost:8001/docs
# - Frontend: http://localhost:3000
# - ChromaDB: http://localhost:8000
# - PostgreSQL: localhost:5432
```

### Git Workflow

```bash
# Create a new feature branch for a ticket
git checkout -b feat/task-description

# Create a bugfix branch
git checkout -b bugfix/task-description

# After completing work, commit and push
git add .
git commit -m "feat: description of changes"
git push origin feat/task-description
```
