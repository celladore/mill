# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Mill** — alpha document and media conversion workspace. The public npm
package is `@celladore/mill`; the Python distribution `xtotext` and import
namespace `xtox` remain compatibility APIs.

## Tech Stack

- **Languages**: Python and JavaScript
- **CLI**: Node launcher (`mill`) plus the compatible Python `xtotext` executable
- **API**: FastAPI REST API (`backend/`)
- **Frontend**: React (`frontend/`)
- **Legacy serverless lane**: Azure Functions (`azure-functions/`)
- **Storage**: Azure Blob Storage and Cosmos DB's MongoDB API
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

- `mill-cli/` and `bin/mill.js` — active Node CLI and npm package
- `backend/` — active FastAPI REST API and conversion services
- `core/` — local deterministic Python conversion engine
- `cli/` and `api/` — legacy Python compatibility entry points
- `azure-functions/` — legacy serverless lane; not the canonical deployed API

## AgentKit Forge

This project has not yet been onboarded to [AgentKit Forge](https://github.com/phoenixvc/agentkit-forge). To request onboarding, [create a ticket](https://github.com/phoenixvc/agentkit-forge/issues/new?title=Onboard+xtox&labels=onboarding).

## Baton Integration

Baton is the shared task graph for cross-repo work. When the `baton` MCP server is available, agents should check for existing work with `task_check` at the start of meaningful tasks, create or claim visible work with `task_notify`/`log_agent_message`, update the task when significant new information becomes available, and log completion or blockers before handing off.
