variable "env" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}
variable "projname" { type = string }

variable "location" {
  type        = string
  description = "Region for compute + data resources (Container App, Key Vault, Cosmos DB, Log Analytics). Cosmos DB free tier and the existing celladore-sub RU-based accounts both run in southafricanorth."
}

variable "swa_location" {
  type        = string
  description = "Region for the Static Web App. Azure Static Web Apps is not offered in southafricanorth; westeurope is the nearest supported region to the compute region."
}

variable "tags" { type = map(string) }

# ── Container image ─────────────────────────────────────────────────────
# No default on purpose. There is no Dockerfile-built image published yet —
# the first `terraform apply` for this module must wait on
# .github/workflows/deploy.yaml having built and pushed at least one image to
# ghcr.io/celladore/xtox-api. Supplying a placeholder default here would let
# `terraform plan` look clean while `apply` fails (or worse, silently
# provisions a Container App that can never start).
variable "container_image" {
  type        = string
  description = "xtox API image, pinned to an immutable digest by the deploy workflow, e.g. ghcr.io/celladore/xtox-api@sha256:<digest>."

  validation {
    condition     = can(regex("^ghcr\\.io/celladore/xtox-api@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be the celladore GHCR xtox-api image pinned to a sha256 digest."
  }
}

variable "container_registry_username" {
  type        = string
  description = "GHCR username for pulling the (private) xtox-api image."
  default     = "celladore"
}

variable "container_registry_password" {
  type        = string
  description = "GHCR read token for pulling the xtox-api image. Empty if the package is public."
  default     = ""
  sensitive   = true
}

# ── Scale ────────────────────────────────────────────────────────────────
variable "min_replicas" {
  type        = number
  description = "Scale-to-zero by default — this is a low-traffic tool, not a gateway with an SLA."
  default     = 0
  validation {
    condition     = var.min_replicas >= 0 && var.min_replicas <= 100
    error_message = "min_replicas must be between 0 and 100."
  }
}

variable "max_replicas" {
  type    = number
  default = 3
  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 100
    error_message = "max_replicas must be between 1 and 100."
  }
}

variable "container_port" {
  type        = number
  description = "Port uvicorn binds inside the container (backend/server.py / backend/Dockerfile)."
  default     = 8000
}

# ── App configuration (backend/config.py env vars) ─────────────────────────
variable "db_name" {
  type        = string
  description = "Mongo database name (DB_NAME)."
  default     = "xtox"
}

variable "allowed_origins" {
  type        = string
  description = "Comma-separated CORS origins (ALLOWED_ORIGINS). backend/server.py treats '*' as dev-mode; set the real frontend origin(s) here for prod."
  default     = "https://xtox.celladoresystems.com"
}

variable "sluice_base_url" {
  type        = string
  description = "Sluice gateway base URL for the transcription passthrough (SLUICE_BASE_URL)."
}

variable "sluice_api_key" {
  type        = string
  description = "Sluice gateway virtual key for the transcription passthrough (SLUICE_API_KEY)."
  sensitive   = true
}

variable "sluice_transcription_model" {
  type        = string
  description = "Model alias to request from sluice (SLUICE_TRANSCRIPTION_MODEL)."
  default     = "whisper"
}

# ── Mystira Identity OIDC (resource-server auth, backend/mystira_auth.py) ──
# Both default to "" so non-production callers remain disabled/fail-closed
# unless they opt in explicitly. Production pins the seeded client values in
# its terraform.tfvars. No client secret variable exists here on purpose —
# celladore-xtox is a Public+PKCE browser client, not a confidential one, so
# xtox's API never holds one.
variable "mystira_oidc_issuer" {
  type        = string
  description = "Mystira Identity OIDC issuer URL (MYSTIRA_OIDC_ISSUER). Empty disables authentication fail-closed."
  default     = ""
}

variable "mystira_oidc_audience" {
  type        = string
  description = "Comma-separated accepted `aud` value(s) for Mystira-issued access tokens (MYSTIRA_OIDC_AUDIENCE). The production audience is celladore-xtox."
  default     = ""
}

# Duplicate of mystira-workspace's oidc-encryption-key (mys-prod-identity-kv).
# Not a client secret: celladore-xtox stays Public+PKCE. ADR-0029 requires every
# resource server to decrypt JWE access tokens locally; xtox copies the 32-byte
# symmetric key into its own vault rather than granting this MI Get on Identity's
# vault (celladore-sub vs Mystira subscription). Rotate by copying the new
# Identity value into TF_VAR_MYSTIRA_OIDC_ENCRYPTION_KEY and applying.
variable "mystira_oidc_encryption_key" {
  type        = string
  description = "Base64-encoded 32-byte OpenIddict encryption key (MYSTIRA_OIDC_ENCRYPTION_KEY). Empty skips wiring; JWE tokens then fail closed with 503."
  default     = ""
  sensitive   = true

  validation {
    condition = var.mystira_oidc_encryption_key == "" || (
      var.mystira_oidc_encryption_key == trimspace(var.mystira_oidc_encryption_key) &&
      can(regex("^[A-Za-z0-9+/]{43}=$", var.mystira_oidc_encryption_key))
    )
    error_message = "mystira_oidc_encryption_key must be empty or a 44-character standard Base64 string (32 decoded bytes) with no surrounding whitespace."
  }
}

variable "mystira_oidc_delegated_audiences" {
  type        = string
  description = "Comma-separated Mystira client audiences allowed only on delegated endpoints with an API-specific scope."
  default     = ""
}

variable "mystira_oidc_transcription_scope" {
  type        = string
  description = "Scope required when a delegated client audience calls /api/transcribe-audio."
  default     = "mill.transcribe"
}

variable "api_custom_domain" {
  type        = string
  description = "Custom hostname for the Container App API. DNS CNAME and asuid TXT records must exist before enabling it."
  default     = "api.xtox.celladoresystems.com"
}

variable "enable_api_custom_domain" {
  type        = bool
  description = "Create the Container Apps custom-domain binding and Azure-managed certificate after DNS validation records resolve."
  default     = false
}

# ── Cosmos DB (MongoDB API, RU-based) ───────────────────────────────────────
variable "cosmos_free_tier_enabled" {
  type        = bool
  description = "Claim the one-per-subscription Cosmos DB free tier discount. Confirmed unclaimed in celladore-sub as of 2026-08-20 (only nex-dev-docs-cosmos-614e6f / nex-prd-docs-cosmos-614e6f exist, both free_tier=false) — verify again before apply if another stack may have claimed it since."
  default     = true
}

variable "cosmos_consistency_level" {
  type        = string
  description = "Cosmos DB default consistency level."
  default     = "Session"
  validation {
    condition     = contains(["Strong", "BoundedStaleness", "Session", "ConsistentPrefix", "Eventual"], var.cosmos_consistency_level)
    error_message = "cosmos_consistency_level must be a valid Cosmos DB consistency level."
  }
}

variable "secrets_expiration_date" {
  type        = string
  description = "Expiration date for Key Vault secrets (ISO-8601 UTC, e.g. 2027-08-20T00:00:00Z)."
  validation {
    condition     = can(regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", var.secrets_expiration_date)) && can(timecmp(var.secrets_expiration_date, "1970-01-01T00:00:00Z")) && timecmp(var.secrets_expiration_date, plantimestamp()) > 0
    error_message = "secrets_expiration_date must be in ISO-8601 UTC format and strictly in the future relative to plan time."
  }
}

variable "key_vault_network_default_action" {
  type        = string
  description = "Key Vault network ACL default action."
  default     = "Allow"
  validation {
    condition     = contains(["Allow", "Deny"], var.key_vault_network_default_action)
    error_message = "key_vault_network_default_action must be 'Allow' or 'Deny'."
  }
}

# ── Static Web App (frontend) ───────────────────────────────────────────────
variable "swa_custom_domain" {
  type        = string
  description = "Custom hostname for the SWA frontend."
  default     = "xtox.celladoresystems.com"
}

# Phase gate for the SWA custom domain binding — deliberately false by
# default. Azure validates a Free-tier SWA custom domain via CNAME, which
# means the DNS record has to exist and resolve to the SWA's default
# hostname *before* the binding resource can succeed. That CNAME is created
# in the celladore-org shared-DNS repo, not here (same "DNS lives elsewhere"
# split sluice uses for litellm.sluice.phoenixvc.tech). Sequence:
#   1. apply with this false        -> creates the SWA, exposes its default
#                                      hostname via the swa_default_hostname
#                                      output
#   2. celladore-org: add a CNAME for var.swa_custom_domain -> that hostname
#   3. confirm the CNAME resolves, then flip this to true and re-apply
# Flipping it before step 2 does not fail softly — the binding resource
# errors out mid-apply.
variable "enable_swa_custom_domain" {
  type        = bool
  description = "Bind swa_custom_domain to the Static Web App. Leave false until the CNAME exists in celladore-org's DNS stack (see comment above)."
  default     = false
}
