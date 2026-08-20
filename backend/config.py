"""
Configuration module for XToX Converter backend.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Database configuration
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

# File storage configuration
TEMP_DIR = Path("/tmp/xtopdf")
DOC_STORAGE_DIR = Path("/tmp/document_storage")

# Application settings
# File size limits
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 10 * 1024 * 1024))  # 10MB default
MAX_AUDIO_FILE_SIZE = int(os.environ.get('MAX_AUDIO_FILE_SIZE', 50 * 1024 * 1024))  # 50MB default

# Timeouts
LATEX_TIMEOUT = int(os.environ.get('LATEX_TIMEOUT', 30))  # seconds
AUDIO_CONVERSION_TIMEOUT = int(os.environ.get('AUDIO_CONVERSION_TIMEOUT', 300))  # 5 minutes

# Rate limiting
RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', 100))  # requests per window
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', 60))  # seconds

# Caching
CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'false').lower() == 'true'
CACHE_TTL = int(os.environ.get('CACHE_TTL', 3600))  # seconds
REDIS_URL = os.environ.get('REDIS_URL')

# Mystira Identity OIDC (resource-server / Bearer-token validation only —
# xtox has no browser login UI of its own, so it never performs the
# interactive authorization_code+PKCE flow; that belongs to whichever client
# actually logs the user in, e.g. the not-yet-built Convert/Transcribe
# frontend registered in mystira-workspace as `celladore-xtox`).
#
# Deliberately unset in every real environment today (infra/env/prod/
# terraform.tfvars leaves both empty): ADR-0029 Addendum 02 is Accepted, but
# the `celladore-xtox` client registration is not seeded yet. See
# backend/mystira_auth.py — auth fails closed (503) whenever either var is
# unset; it never falls back to a bypass.
MYSTIRA_OIDC_ISSUER = os.environ.get('MYSTIRA_OIDC_ISSUER')
# Comma-separated list of acceptable `aud` values.
MYSTIRA_OIDC_AUDIENCE = os.environ.get('MYSTIRA_OIDC_AUDIENCE')

# Sluice transcription gateway (speech-to-text is routed through sluice's
# OpenAI-compatible gateway rather than calling Azure OpenAI Whisper directly —
# see backend/services/transcription_service.py. Unset until sluice ships
# POST /v1/audio/transcriptions (Baton task 833d6a98).
SLUICE_BASE_URL = os.environ.get('SLUICE_BASE_URL')
SLUICE_API_KEY = os.environ.get('SLUICE_API_KEY')
# Must match the model_name sluice's LiteLLM config registers for the Foundry
# Whisper deployment (infra/modules/sluice_aca/main.tf in celladore/sluice) —
# that module only ever registers "foundry-whisper", never a bare "whisper"
# alias, and the xtox virtual key's model allowlist (scripts/keys.yaml in
# celladore/sluice) only permits "foundry-whisper". A bare "whisper" default
# here 404s against sluice regardless of the allowlist.
SLUICE_TRANSCRIPTION_MODEL = os.environ.get('SLUICE_TRANSCRIPTION_MODEL', 'foundry-whisper')
SLUICE_TRANSCRIBE_TIMEOUT = int(os.environ.get('SLUICE_TRANSCRIBE_TIMEOUT', 120))  # seconds

# Create necessary directories
TEMP_DIR.mkdir(exist_ok=True)
DOC_STORAGE_DIR.mkdir(exist_ok=True)
