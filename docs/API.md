# Mill API Documentation

## Base URL

```
http://localhost:8000/api
```

## Authentication

Most endpoints require authentication via JWT token in the Authorization header:

```
Authorization: Bearer <token>
```

## Endpoints

### LaTeX Conversion

#### POST /convert

Convert a LaTeX file to PDF.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body:
  - `file`: LaTeX file (.tex)
  - Query parameter: `auto_fix` (boolean, optional)

**Response:**
```json
{
  "id": "conversion-id",
  "filename": "document",
  "success": true,
  "auto_fix_applied": false,
  "errors": [],
  "warnings": [],
  "pdf_path": "/tmp/xtopdf/conversion-id.pdf",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

**Error Responses:**
- `400`: Invalid file format or validation error
- `413`: File too large
- `408`: Conversion timeout
- `500`: Server error

#### GET /download/{conversion_id}

Download the converted PDF file.

**Response:**
- Content-Type: `application/pdf`
- File download

### Audio Conversion

#### POST /convert-audio

Convert an audio file (especially WhatsApp OGG Opus) to another format.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body:
  - `file`: Audio file
  - Query parameters:
    - `target_format`: mp3, wav, ogg, m4a, aac, flac (default: mp3)
    - `bitrate`: 128k, 192k, 256k, 320k (default: 192k)
    - `sample_rate`: Optional sample rate in Hz

**Response:**
```json
{
  "id": "conversion-id",
  "filename": "audio",
  "original_format": "ogg",
  "target_format": "mp3",
  "success": true,
  "errors": [],
  "warnings": [],
  "audio_path": "/tmp/xtopdf/conversion-id.mp3",
  "file_size_kb": 1024.5,
  "duration": 120.5,
  "timestamp": "2025-01-01T00:00:00Z"
}
```

#### GET /download-audio/{conversion_id}

Download the converted audio file.

### Batch Conversion

#### POST /batch/convert-latex

Convert multiple LaTeX files in batch.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: Multiple `files` (up to 50)
- Query parameter: `auto_fix` (boolean)

**Response:**
```json
{
  "batch_id": "batch-id",
  "total_files": 5,
  "successful": 4,
  "failed": 1,
  "results": [...],
  "errors": [...]
}
```

#### POST /batch/convert-audio

Convert multiple audio files in batch (up to 20 files).

### Conversion History

#### GET /history/conversions

Get conversion history.

**Query Parameters:**
- `limit`: Number of results (1-100, default: 50)
- `offset`: Pagination offset (default: 0)

#### GET /history/audio-conversions

Get audio conversion history.

#### GET /history/conversions/{conversion_id}

Get specific conversion by ID.

#### DELETE /history/conversions/{conversion_id}

Delete a conversion from history.

### Webhooks

#### POST /webhooks/register

Register a webhook URL for conversion notifications.

**Request:**
```json
{
  "url": "https://your-domain.com/webhook",
  "events": ["conversion.completed", "conversion.failed"],
  "secret": "optional-secret-for-signature"
}
```

## Error Response Format

All errors follow this format:

```json
{
  "error": {
    "type": "error_type",
    "status_code": 400,
    "message": "Error message",
    "path": "/api/endpoint"
  }
}
```

## Rate Limiting

Rate limits are applied per IP address:
- Default: 100 requests per minute
- Headers:
  - `X-RateLimit-Limit`: Maximum requests
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset time (Unix timestamp)

## OpenAPI Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

