env      = "prod"
projname = "xtox"
location = "southafricanorth"

swa_location = "westeurope"

tags = {
  owner   = "xtox-team"
  project = "xtox"
  env     = "prod"
}

# No image published yet — .github/workflows/deploy.yaml must build and push
# ghcr.io/celladore/xtox-api at least once before this can be set and the
# first `terraform apply` attempted. Deliberately left unset here (and the
# module variable has no default either) so a real `terraform apply` without
# it fails loudly instead of silently deploying nothing. terraform-plan in CI
# supplies its own plan-only sentinel digest via -var (see deploy.yaml) so PRs
# can still plan cleanly before this is ever set — that sentinel is never
# used by terraform-apply, which always passes the real build digest.
# container_image = "ghcr.io/celladore/xtox-api@sha256:<digest>"

# Public GHCR package assumed — no registry credentials needed. Set
# TF_VAR_container_registry_password (CI secret) if the package is made
# private instead of committing a value here.

min_replicas = 0 # scale-to-zero — low-traffic tool, not a gateway with an SLA
max_replicas = 3

db_name         = "xtox"
allowed_origins = "https://xtox.celladoresystems.com"

# Sluice's transcription passthrough (backend/services/transcription_service.py,
# Baton task 833d6a98). sluice_base_url is not a secret; sluice_api_key is
# supplied via TF_VAR_sluice_api_key (CI secret) and intentionally absent here.
sluice_base_url            = "https://litellm.sluice.phoenixvc.tech"
sluice_transcription_model = "whisper"

cosmos_free_tier_enabled = true
cosmos_consistency_level = "Session"

# Rotate before expiration; alerting/rotation job must reference this. See
# sluice's ops runbook pattern (infra/env/prod/terraform.tfvars there).
secrets_expiration_date = "2027-08-20T00:00:00Z"

swa_custom_domain = "xtox.celladoresystems.com"
# Leave false until celladore-org's DNS stack has a CNAME for
# xtox.celladoresystems.com pointing at the SWA's default hostname (output
# swa_default_hostname after the first apply). See the variable's
# description in infra/modules/xtox_api_aca/variables.tf for the full
# two-phase sequence and why flipping this early fails apply, not plan.
enable_swa_custom_domain = false
