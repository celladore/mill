# celladore-sub. Pinned as a validated default rather than left free-form —
# see the provider block comment in main.tf for why this exists at all.
variable "subscription_id" {
  type        = string
  description = "Target Azure subscription. Must be celladore-sub — this stack must never target sluice's separate bb4e3882 production subscription."
  default     = "614e6f86-e401-4bdf-8479-a59986e18815"

  validation {
    condition     = var.subscription_id == "614e6f86-e401-4bdf-8479-a59986e18815"
    error_message = "subscription_id must be celladore-sub (614e6f86-e401-4bdf-8479-a59986e18815). If you need to target a different subscription, that is a deliberate decision this validation is designed to force you to make explicitly — edit this rule, don't just override the var."
  }
}

variable "env" {
  type    = string
  default = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "projname" {
  type    = string
  default = "xtox"
}

variable "location" {
  type    = string
  default = "southafricanorth"
}

variable "swa_location" {
  type        = string
  default     = "eastus2"
  description = "Azure Static Web Apps is not offered in southafricanorth. westeurope was tried first and rejected outright by Azure (403 RequestDisallowedByAzure: \"region is currently not accepting new customers\") on celladore-sub during the first real apply. eastus2 is sluice's own working region for the same constraint on this subscription (marketing_swa_location in celladore/sluice's infra/env/prod-celladore/terraform.tfvars) — not a guess."
}

variable "tags" {
  type = map(string)
  default = {
    owner   = "xtox-team"
    project = "xtox"
    env     = "prod"
  }
}

variable "container_image" {
  type        = string
  description = "See infra/modules/xtox_api_aca/variables.tf — no default on purpose; must be supplied once .github/workflows/deploy.yaml has published an image."
}

variable "container_registry_username" {
  type    = string
  default = "celladore"
}

variable "container_registry_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "min_replicas" {
  type    = number
  default = 0
}

variable "max_replicas" {
  type    = number
  default = 3
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "db_name" {
  type    = string
  default = "xtox"
}

variable "allowed_origins" {
  type    = string
  default = "https://mill.celladoresystems.com"
}

variable "sluice_base_url" {
  type        = string
  description = "Sluice gateway base URL for the transcription passthrough."
}

variable "sluice_api_key" {
  type      = string
  sensitive = true
}

variable "sluice_transcription_model" {
  type        = string
  default     = "foundry-whisper"
  description = "Must match the model_name sluice's LiteLLM config registers (infra/modules/sluice_aca/main.tf in celladore/sluice) and the xtox virtual key's allowlist (scripts/keys.yaml there) — currently \"foundry-whisper\" only, no bare \"whisper\" alias exists."
}

variable "mystira_oidc_issuer" {
  type        = string
  default     = ""
  description = "Mystira Identity issuer. Production pins the live discovery issuer in terraform.tfvars."
}

variable "mystira_oidc_audience" {
  type        = string
  default     = ""
  description = "Accepted Mystira access-token audience. Production pins the seeded Public + PKCE client id in terraform.tfvars."
}

variable "mystira_oidc_encryption_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Duplicate of Identity's oidc-encryption-key. For direct Terraform runs, pass via TF_VAR_mystira_oidc_encryption_key; for GitHub Actions, supplied via secret TF_VAR_MYSTIRA_OIDC_ENCRYPTION_KEY — never commit the value."
}

variable "mystira_oidc_delegated_audiences" {
  type        = string
  default     = ""
  description = "Mystira client audiences allowed only for explicitly scoped delegated XtOX operations."
}

variable "mystira_oidc_transcription_scope" {
  type        = string
  default     = "mill.transcribe"
  description = "Mystira scope required for cross-client transcription calls."
}

variable "mystira_oidc_render_audiences" {
  type        = string
  default     = ""
  description = "Mystira client audiences allowed only for explicitly scoped LaTeX rendering."
}

variable "mystira_oidc_render_scope" {
  type        = string
  default     = "mill.render"
  description = "Mystira scope required for cross-client LaTeX rendering."
}

variable "api_custom_domain" {
  type        = string
  description = "Custom hostname for the XtOX Container App API."
  default     = "api.mill.celladoresystems.com"
}

variable "enable_api_custom_domain" {
  type        = bool
  description = "Enable only after the API CNAME and asuid TXT records resolve."
  default     = false
}

variable "cosmos_free_tier_enabled" {
  type    = bool
  default = true
}

variable "cosmos_consistency_level" {
  type    = string
  default = "Session"
}

variable "secrets_expiration_date" {
  type        = string
  description = "ISO-8601 UTC. Rotate before expiration; see sluice's ops runbook pattern."
}

variable "swa_custom_domain" {
  type    = string
  default = "mill.celladoresystems.com"
}

variable "enable_swa_custom_domain" {
  type        = bool
  default     = false
  description = "See infra/modules/xtox_api_aca/variables.tf for the two-phase DNS sequencing this gates."
}
