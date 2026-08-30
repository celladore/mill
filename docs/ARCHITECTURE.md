# Architecture Documentation

## System Overview

Mill is a multi-format document and media conversion platform built with a microservices architecture.

## Architecture Diagram

```
┌─────────────────┐
│   React Frontend │
│   (Port 3000)    │
└────────┬─────────┘
         │ HTTP/REST
         │
┌────────▼─────────────────────────────────┐
│         FastAPI Backend                  │
│         (Port 8000)                      │
│  ┌──────────────────────────────────┐   │
│  │  API Routes                      │   │
│  │  - /api/convert                  │   │
│  │  - /api/convert-audio            │   │
│  │  - /api/batch/*                  │   │
│  │  - /api/history/*                │   │
│  └──────────┬───────────────────────┘   │
│             │                            │
│  ┌──────────▼───────────────────────┐   │
│  │  Services Layer                  │   │
│  │  - LatexService                  │   │
│  │  - AudioService                  │   │
│  └──────────┬───────────────────────┘   │
│             │                            │
│  ┌──────────▼───────────────────────┐   │
│  │  Core Converters                 │   │
│  │  - AudioConverter                │   │
│  │  - ImageConverter                │   │
│  └──────────────────────────────────┘   │
└────────┬─────────────────────────────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    │         │              │             │
┌───▼───┐ ┌──▼────┐   ┌─────▼─────┐  ┌───▼────┐
│MongoDB│ │FFmpeg │   │ pdflatex  │  │  File  │
│       │ │       │   │           │  │ Storage│
└───────┘ └───────┘   └───────────┘  └────────┘
```

## Component Descriptions

### Frontend (React)

- **Location:** `frontend/`
- **Technology:** React 19, Tailwind CSS, Axios
- **Responsibilities:**
  - User interface for file upload
  - Conversion status display
  - File download
  - Error handling and user feedback

### Backend API (FastAPI)

- **Location:** `backend/`
- **Technology:** FastAPI, Uvicorn, Motor (MongoDB)
- **Responsibilities:**
  - REST API endpoints
  - Request validation
  - Business logic orchestration
  - Database operations
  - File processing coordination

### Core Converters

- **Location:** `core/` (published under the compatible `xtox.core` import)
- **Components:**
  - `AudioConverter`: Handles audio format conversion
  - `ImageConverter`: Handles image format conversion
  - `DocumentConverter`: Handles document format conversion

### Services Layer

- **Location:** `backend/services/`
- **Components:**
  - `LatexService`: LaTeX to PDF conversion logic
  - `AudioService`: Audio conversion orchestration

### Database (MongoDB)

- **Collections:**
  - `conversions`: LaTeX conversion results
  - `audio_conversions`: Audio conversion results
  - `documents`: Document metadata
  - `webhooks`: Webhook configurations

### External Dependencies

- **FFmpeg:** Audio/video processing
- **pdflatex:** LaTeX compilation
- **Pillow:** Image processing

## Data Flow

### LaTeX Conversion Flow

1. User uploads `.tex` file via frontend
2. Frontend sends POST to `/api/convert`
3. Backend validates file
4. `LatexService` processes file:
   - Creates temp directory
   - Writes LaTeX file
   - Executes pdflatex
   - Parses errors/warnings
   - Moves PDF to storage
5. Result stored in MongoDB
6. Response returned to frontend
7. User downloads PDF

### Audio Conversion Flow

1. User uploads audio file
2. Frontend sends POST to `/api/convert-audio`
3. Backend validates file
4. `AudioService` processes file:
   - Creates temp directory
   - Saves uploaded file
   - Uses `AudioConverter` (FFmpeg/pydub)
   - Converts to target format
   - Moves converted file to storage
5. Result stored in MongoDB
6. Response returned to frontend

## Security Architecture

- **Authentication:** JWT tokens (production)
- **Authorization:** User-based permissions
- **File Security:** Path sanitization, size limits
- **CORS:** Configurable allowed origins
- **Rate Limiting:** Per-IP request limits

## Scalability Considerations

- **Horizontal Scaling:** Stateless API servers
- **Database:** MongoDB replica sets
- **File Storage:** Azure Blob Storage (cloud)
- **Caching:** Redis (optional)
- **Job Queue:** Celery/Redis (for batch processing)

## Deployment Options

1. **Local Development:** Docker Compose
2. **Cloud:** Azure Functions (serverless)
3. **Traditional:** Docker containers on VMs
4. **Kubernetes:** Container orchestration

## Monitoring and Observability

- **Logging:** Structured logging with Python logging
- **Metrics:** Application performance metrics
- **Error Tracking:** Integration-ready for Sentry
- **Liveness:** `/api/health` confirms the API process is serving.
- **Dependency readiness:** `/api/ready` confirms the configured database responds.
- **Persisted status records:** `/api/status` is CRUD data, not a deployment probe.

