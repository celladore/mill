"""
Configuration module for the Mill conversion backend.
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
AZURE_STORAGE_ACCOUNT_URL = os.environ.get('AZURE_STORAGE_ACCOUNT_URL')
AZURE_STORAGE_CONTAINER = os.environ.get('AZURE_STORAGE_CONTAINER', 'documents')
AZURE_ARTIFACT_CONTAINER = os.environ.get('AZURE_ARTIFACT_CONTAINER', 'artifacts')
AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')

# Application settings
# File size limits
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 10 * 1024 * 1024))  # 10MB default
MAX_AUDIO_FILE_SIZE = int(os.environ.get('MAX_AUDIO_FILE_SIZE', 50 * 1024 * 1024))  # 50MB default
MAX_IMAGE_FILE_SIZE = int(os.environ.get('MAX_IMAGE_FILE_SIZE', 20 * 1024 * 1024))  # 20MB default
MAX_VIDEO_FILE_SIZE = int(os.environ.get('MAX_VIDEO_FILE_SIZE', 100 * 1024 * 1024))  # 100MB default

# Timeouts
LATEX_TIMEOUT = int(os.environ.get('LATEX_TIMEOUT', 30))  # seconds
AUDIO_CONVERSION_TIMEOUT = int(os.environ.get('AUDIO_CONVERSION_TIMEOUT', 300))  # 5 minutes
VIDEO_CONVERSION_TIMEOUT = int(os.environ.get('VIDEO_CONVERSION_TIMEOUT', 300))  # 5 minutes
if VIDEO_CONVERSION_TIMEOUT <= 0:
    raise ValueError('VIDEO_CONVERSION_TIMEOUT must be a positive integer')

# Rate limiting
RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', 100))  # requests per window
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', 60))  # seconds

# Caching
CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'false').lower() == 'true'
CACHE_TTL = int(os.environ.get('CACHE_TTL', 3600))  # seconds
REDIS_URL = os.environ.get('REDIS_URL')

# Mystira Identity OIDC (resource-server / Bearer-token validation only —
# The frontend performs the interactive authorization_code+PKCE flow as the
# Public client `celladore-xtox`; this API only validates the resulting
# Bearer access token. Production pins the seeded issuer and audience in
# Terraform. Missing configuration still fails closed (503) and never falls
# back to a bypass.
MYSTIRA_OIDC_ISSUER = os.environ.get('MYSTIRA_OIDC_ISSUER')
# Comma-separated list of acceptable `aud` values.
MYSTIRA_OIDC_AUDIENCE = os.environ.get('MYSTIRA_OIDC_AUDIENCE')
# Base64-encoded 32-byte OpenIddict symmetric key (duplicate of Identity's
# oidc-encryption-key). Required to decrypt JWE access tokens; not a client secret.
MYSTIRA_OIDC_ENCRYPTION_KEY = os.environ.get('MYSTIRA_OIDC_ENCRYPTION_KEY')

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

# Generative text is a separate, governed Sluice lane. It remains dark until
# Sluice grants the mill virtual key access to the server-owned alias and the
# deployment explicitly enables it (Baton c11a14ee blocks Mill c3238372).
GENERATIVE_TEXT_ENABLED = os.environ.get('GENERATIVE_TEXT_ENABLED', 'false').lower() == 'true'
SLUICE_TEXT_MODEL = os.environ.get('SLUICE_TEXT_MODEL', 'mill-text-v1')
SLUICE_TEXT_TIMEOUT = int(os.environ.get('SLUICE_TEXT_TIMEOUT', 45))
SLUICE_TEXT_MAX_ATTEMPTS = int(os.environ.get('SLUICE_TEXT_MAX_ATTEMPTS', 3))

if SLUICE_TEXT_TIMEOUT <= 0:
    raise ValueError('SLUICE_TEXT_TIMEOUT must be a positive integer')
if not 1 <= SLUICE_TEXT_MAX_ATTEMPTS <= 5:
    raise ValueError('SLUICE_TEXT_MAX_ATTEMPTS must be between 1 and 5')

# Generated artifact retention. Blobs expire after seven days while Mongo
# history remains queryable and is marked non-downloadable.
CONVERSION_RETENTION_SECONDS = int(
    os.environ.get('CONVERSION_RETENTION_SECONDS', 7 * 24 * 3600)
)  # 7d default
CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS = int(
    os.environ.get('CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS', 3600)
)  # 1h default

# A zero or negative value here would make RetentionService.run_forever()
# loop with no effective delay, hammering the database continuously -- fail
# fast at config-load time rather than lazily inside the sweep loop.
if CONVERSION_RETENTION_SECONDS <= 0:
    raise ValueError(
        'CONVERSION_RETENTION_SECONDS must be a positive integer, '
        f'got {CONVERSION_RETENTION_SECONDS}'
    )
if CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS <= 0:
    raise ValueError(
        'CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS must be a positive integer, '
        f'got {CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS}'
    )

# Create necessary directories
TEMP_DIR.mkdir(exist_ok=True)
