# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**xtotext (xtox)** — AI-ready document conversion system. Transforms any document (PDF, DOCX, LaTeX, Markdown, etc.) into AI-optimized text formats for LLM consumption. Includes document storage and permission-based access.

## Tech Stack

- **Language**: Python
- **CLI**: Click-based CLI tool
- **API**: FastAPI REST API (`api/`)
- **Serverless**: Azure Functions (`azure-functions/`)
- **Storage**: Azure Data Lake Storage Gen2
- **Build**: Makefile

## Key Commands

```bash
make install              # Install package in dev mode (pip install -e .)
make dev-install          # Install with dev dependencies
make test                 # Run tests
make test-cov             # Run tests with coverage
make lint                 # Lint
make format               # Format code
make build                # Build package
make run-example          # Run example conversion
make md-to-pdf            # Convert markdown to PDF
```

## Architecture

- `cli/` — Click CLI for document conversion
- `api/` — FastAPI REST API
- `azure-functions/` — Serverless conversion endpoints
- `backend/` — Core conversion logic

## AgentKit Forge

This project has not yet been onboarded to [AgentKit Forge](https://github.com/phoenixvc/agentkit-forge). To request onboarding, [create a ticket](https://github.com/phoenixvc/agentkit-forge/issues/new?title=Onboard+xtox&labels=onboarding).

## Baton Integration

Baton is the shared task graph for cross-repo work. When the `baton` MCP server is available, agents should check for existing work with `task_check` at the start of meaningful tasks, create or claim visible work with `task_notify`/`log_agent_message`, update the task when significant new information becomes available, and log completion or blockers before handing off.
