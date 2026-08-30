# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Mill is an alpha document and media conversion workspace with a FastAPI backend
and React frontend. The Python distribution `xtotext`, import namespace `xtox`,
and older path examples in this guide are compatibility surfaces retained for
existing consumers.

## Common Commands

### Development Setup
```powershell
# Install package in development mode with all dependencies
make setup
# Or manually:
pip install -e ".[dev,azure,api]"
```

### Testing
```powershell
# Run all tests
make test
pytest

# Run tests with coverage report
make test-cov
pytest --cov=xtox --cov-report=html --cov-report=term

# Run single test file
pytest tests/test_md_to_pdf.py

# Run single test function
pytest tests/test_md_to_pdf.py::test_document_converter_init
```

### Code Quality
```powershell
# Run linting (flake8 + mypy)
make lint

# Run only flake8
flake8 xtox

# Run only mypy type checking
mypy xtox

# Format code (black + isort)
make format
```

### Frontend Development
```powershell
# Navigate to frontend directory
cd xtox/frontend

# Start development server
npm start
# Or with yarn:
yarn start

# Build for production
npm run build

# Run linting
npm run lint:check
npm run lint  # with auto-fix

# Format code
npm run format:check
npm run format  # with auto-fix
```

### Backend Development
```powershell
# Run FastAPI backend locally
cd xtox/backend
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Azure Functions Development
```powershell
# Navigate to Azure Functions directory
cd xtox/azure-functions

# Install Azure Functions Core Tools (if not installed)
npm install -g azure-functions-core-tools@4

# Start functions locally
func start
```

### CLI Usage
```powershell
# Convert Markdown to PDF
xtotext input.md -o output_dir -r 2

# Convert with specific format
xtotext input.md --format docx
xtotext input.md --format html

# Convert LaTeX to PDF
xtotext document.tex -o output_dir

# Batch processing
xtotext file1.md file2.md file3.md --batch

# Interactive mode
xtotext input.md -i

# Verbose output
xtotext input.md -v
```

## Architecture

### High-Level Structure
The project uses a modular architecture with clear separation between:
- **Core conversion logic** (`xtox/core/`) - Document transformation engines
- **API layer** (`xtox/api/`, `xtox/backend/`, `xtox/azure-functions/`) - RESTful endpoints
- **Frontend** (`xtox/frontend/`) - React application with Tailwind CSS
- **CLI** (`xtox/cli/`) - Command-line interface
- **Utilities** (`xtox/utils/`) - Shared utilities (image handling, etc.)
- **Workflows** (`xtox/workflows/`) - High-level orchestration
- **Shared Libraries** (`lib/`) - Reusable TypeScript/JavaScript libraries

### Key Components

#### Core Package (`xtox/core/`)
Contains the main conversion engines:
- `document_converter.py` - Main orchestrator class (`DocumentConverter`)
- `markdown_to_latex.py` - Markdown → LaTeX conversion
- `markdown_to_docx.py` - Markdown → DOCX conversion
- `markdown_to_html.py` - Markdown → HTML conversion
- `html_to_markdown.py` - HTML → Markdown conversion
- `latex_to_pdf.py` - LaTeX → PDF conversion with auto-fixing

The `DocumentConverter` class is the primary interface for conversions, providing methods like:
- `markdown_to_pdf(markdown_path, output_dir, refinement_level)`
- `latex_to_pdf(latex_path, auto_fix)`
- `markdown_to_docx(markdown_path, output_dir)`
- `markdown_to_html(markdown_path, output_dir)`

#### Backend (`xtox/backend/`)
FastAPI-based backend with:
- `server.py` - Main FastAPI app with CORS, rate limiting, error handling
- `database.py` - MongoDB connection manager with connection pooling and index management
- `config.py` - Environment-based configuration
- `routers/` - Modular route handlers:
  - `conversion.py` - Document conversion endpoints
  - `documents.py` - Document management
  - `batch.py` - Batch processing
  - `history.py` - Conversion history
  - `webhooks.py` - Webhook integrations
- `services/` - Business logic layer:
  - `conversion_service.py` - Conversion orchestration
- `middleware/` - Custom middleware (rate limiting, error handling)

Database uses Motor (async MongoDB driver) with connection pooling configured via environment variables:
- `MONGODB_MAX_POOL_SIZE` (default: 100)
- `MONGODB_MIN_POOL_SIZE` (default: 0)
- `MONGODB_MAX_IDLE_TIME_MS` (default: 0)

#### Azure Functions (`xtox/azure-functions/`)
Serverless functions for cloud deployment:
- `function_app.py` - FastAPI app integrated with Azure Functions
- Individual function directories:
  - `ConvertToAIText/` - AI-optimized text conversion
  - `ConvertLatexToPdf/` - LaTeX to PDF conversion
  - `ConvertMarkdownToPdf/` - Markdown to PDF conversion
  - `UploadDocument/` - Document upload handler
  - `DownloadDocument/` - Document download handler
  - `ListDocuments/` - Document listing
- `shared_code/` - Reusable code for functions
- `routers/` - Route definitions for FastAPI integration

Architecture Decision: Pure Python Azure Functions was chosen over C#, hybrid approaches, or Azure ML integration for:
- Superior AI library ecosystem
- Fastest development path
- Simpler single-language architecture
- Lower operational complexity

#### Frontend (`xtox/frontend/`)
React application with:
- `package.json` - Uses React 19, React Router, Axios, Tailwind CSS
- Build system: Create React App with CRACO for customization
- `src/App.js` - Main application component
- `src/components/` - Reusable React components
- Design system: Tailwind CSS with custom configuration and design tokens

#### CLI (`xtox/cli/main.py`)
Command-line interface supporting:
- Single file conversions
- Batch processing (`--batch`)
- Interactive mode (`-i`)
- Multiple output formats (PDF, LaTeX, DOCX, HTML, image formats)
- Refinement levels for LaTeX (0-3)
- Use case targeting (`--use-case web|print|archive|editing|ai_processing`)

#### Transcription Library (`lib/transcription/`)
Shared TypeScript library for Azure OpenAI Whisper transcription:
- `@xtox/transcription-service` - npm package for audio-to-text conversion
- Used by dependent projects (e.g., WhatsSummarize)
- Supports multiple audio formats (opus, ogg, mp3, wav, m4a, webm, flac)
- Provides TypeScript types and definitions
- Build output in `dist/` directory

Build commands:
```powershell
cd lib/transcription
npm install
npm run build          # Build TypeScript to JavaScript
npm run build:watch    # Watch for changes
npm run clean          # Clean build artifacts
```

Environment variables for transcription:
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY` - API key
- `AZURE_OPENAI_DEPLOYMENT_NAME` - Whisper deployment name
- `AZURE_OPENAI_API_VERSION` - API version (optional, default: 2024-02-15-preview)

### Data Flow

**Document Conversion Flow:**
1. Input document received via CLI, API, or Azure Function
2. `DocumentConverter` routes to appropriate converter
3. For Markdown→PDF:
   - Extract and copy images to output directory
   - Convert Markdown → LaTeX
   - Apply refinements if `refinement_level > 0`
   - Compile LaTeX → PDF using pdflatex
4. Result returned with paths to generated files

**API Request Flow:**
1. Request hits FastAPI server or Azure Function
2. Rate limiting middleware checks request limits
3. Error handling middleware wraps request
4. Router dispatches to appropriate handler
5. Service layer performs business logic
6. Database layer handles persistence (MongoDB)
7. Response returned with appropriate status codes

### Storage Architecture
- **Local storage**: MongoDB for metadata, conversion history, permissions
- **Azure Storage**: Data Lake Storage Gen2 for documents and converted files
- **Temporary files**: `/tmp/xtopdf` for processing, `/tmp/document_storage` for staging

## Development Practices

### Type Hints
The codebase uses extensive type hints. All new functions should include proper type annotations:
```python
from typing import Dict, Optional, Union
from pathlib import Path

def convert_document(
    input_path: Union[str, Path], 
    output_dir: Optional[str] = None
) -> Dict[str, str]:
    ...
```

### Testing Requirements
- Tests use pytest framework
- Configuration in `pyproject.toml`
- Test files must match `test_*.py` pattern
- Test classes must start with `Test*`
- Test functions must start with `test_*`
- Tests that require pdflatex should use `@pytest.mark.skipif` decorator

### Error Handling
The backend uses centralized error handling middleware. Custom exceptions should be raised and caught at the middleware level. Azure Functions should return appropriate HTTP responses with error details.

### Configuration Management
Environment variables are loaded via `python-dotenv`:
- Backend: `xtox/backend/.env`
- Azure Functions: `xtox/azure-functions/local.settings.json`

Critical production variables:
- `JWT_SECRET_KEY` - Minimum 32 characters
- `MONGO_URL` - MongoDB connection string
- `ALLOWED_ORIGINS` - Comma-separated frontend URLs (use `*` only in dev)
- `ENVIRONMENT` - Set to `production` for prod
- `ALLOW_MOCK_AUTH` - Must be `false` in production

### Security Considerations
- JWT tokens for authentication (no mock auth in production)
- CORS origin restrictions (configure `ALLOWED_ORIGINS`)
- File path sanitization to prevent path traversal
- Input validation on all endpoints
- Rate limiting enabled by default
- Secrets managed via environment variables and Azure Key Vault

## Infrastructure

### Azure Deployment
Infrastructure as Code using Bicep templates (`infra/bicep/`):
- `main.bicep` - Main infrastructure template
- `functionApp.bicep` - Azure Functions configuration
- `storageAccount.bicep` - Storage account setup
- `keyVault.bicep` - Key Vault for secrets
- `appInsights.bicep` - Application monitoring

Deploy using PowerShell scripts in `infra/`:
- `deploy-infrastructure.ps1` - Full deployment
- `deploy-infrastructure-safe.ps1` - Safe deployment with validation
- `deploy.ps1` - Simplified deployment

### Environments
Parameter files for different environments:
- `parameters.dev.bicepparam` - Development
- `parameters.test.bicepparam` - Testing
- `parameters.prod.bicepparam` - Production

## Dependencies

### Python Dependencies
Core:
- `pathlib`, `Pillow`, `python-docx` - Document processing
- `pytest`, `pytest-cov`, `black`, `flake8`, `mypy` - Development tools
- `azure-functions`, `azure-storage-blob`, `azure-identity` - Azure integration
- `fastapi`, `uvicorn`, `pydantic` - API framework
- `motor` - Async MongoDB driver
- `pydub` - Audio conversion (requires FFmpeg installed separately)

### Frontend Dependencies
- React 19 with React Router
- Axios for HTTP requests
- Tailwind CSS for styling
- CRACO for CRA customization
- ESLint and Prettier for code quality

### External Tools Required
- **pdflatex** (TeX Live, MiKTeX, or MacTeX) - Required for PDF generation
- **FFmpeg** - Required for audio conversion features
- **Node.js 14+** - For frontend development
- **Python 3.9+** - For backend development
- **MongoDB** - For data persistence
- **Azure CLI or PowerShell Az module** - For Azure deployment

## AI-Specific Features

### LLM Optimization
The system includes specialized AI text optimization features:
- Token-aware chunking for different LLM models (GPT-4, Claude-3, GPT-3.5)
- Context preservation with semantic chunking strategies
- Configurable formatting (code blocks, headers, file paths, hierarchy)
- Model-specific tokenizers and limits

### Repository Processing
Batch conversion of entire codebases/documentation sets:
- Pattern-based file inclusion/exclusion
- Directory structure preservation
- Git information integration (optional)
- Consolidated output for LLM consumption

Configuration via YAML files in `config/` directory (when present).

## Important Notes

### Makefile Commands (Unix-style)
The Makefile uses Unix commands (`rm -rf`, `find`). On Windows:
- Use Git Bash, WSL, or equivalent Unix shell
- Or run equivalent PowerShell commands directly

### Package Installation
Always use development mode for local work:
```powershell
pip install -e ".[dev,azure,api]"
```
This allows changes to be reflected immediately without reinstallation.

### Database Indexes
Indexes are created automatically on application startup via `Database._create_indexes()`. For production, consider moving index creation to a separate migration script to avoid startup overhead.

### CORS Configuration
The backend defaults to allowing all origins (`*`) in development. Always configure specific origins via `ALLOWED_ORIGINS` environment variable before production deployment.

## File Organization

Key directories:
- `xtox/` - Main Python package (installable)
- `lib/` - Shared libraries (TypeScript/JavaScript)
  - `transcription/` - Azure OpenAI Whisper transcription service
- `tests/` - Test files (pytest)
- `examples/` - Example usage scripts
- `test_data/` - Sample files for testing
- `docs/` - Documentation (API, Architecture, Testing, Design System)
- `infra/` - Infrastructure as Code (Bicep templates, deployment scripts)
- `public/` - Static assets
- `.github/` - GitHub Actions workflows (if present)
- `.cursor/`, `.emergent/` - IDE configurations

Top-level config files:
- `setup.py` - Package setup and dependencies
- `pyproject.toml` - Modern Python config (black, isort, pytest, mypy)
- `requirements.txt` - Consolidated dependencies
- `Makefile` - Development tasks
- `.gitignore` - Version control exclusions
- `cspell.config.json` - Spell checking configuration
