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

```bash
# Start all services (PostgreSQL, ChromaDB, Ollama)
docker compose up -d

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f postgres

# Stop services
docker compose down

# Rebuild and restart
docker compose up -d --build

# Check service status
docker compose ps
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
