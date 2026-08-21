env      = "prod"
projname = "xtox"
location = "southafricanorth"

swa_location = "eastus2"
# westeurope was the original guess (nearest region to southafricanorth) but
# the first real apply hit a hard 403 there: RequestDisallowedByAzure,
# "region is currently not accepting new customers" for celladore-sub.
# eastus2 is sluice's own working region for this exact constraint on the
# same subscription (marketing_swa_location in celladore/sluice's
# infra/env/prod-celladore/terraform.tfvars) — verified precedent, not a guess.

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

# ghcr.io/celladore/xtox-api is private (verified via
# `gh api orgs/celladore/packages/container/xtox-api --jq '.visibility'`,
# not assumed) — GHCR packages default to private on first push via a
# workflow's GITHUB_TOKEN, and nothing here ever flipped that. The first
# real apply failed pulling the image into the Container App with
# "UNAUTHORIZED: authentication required" as a result. container_registry_password
# is supplied via TF_VAR_container_registry_password (CI secret, see
# deploy.yaml's terraform-apply job) and intentionally absent here — same
# pattern celladore/docket uses for its own private docket-api package
# (GHCR_TOKEN secret -> TF_VAR_ghcr_token in docket's terraform-apply.yml).

min_replicas = 0 # scale-to-zero — low-traffic tool, not a gateway with an SLA
max_replicas = 3

db_name         = "xtox"
allowed_origins = "https://xtox.celladoresystems.com"

# Mystira Identity production client seeded by phoenixvc/mystira-workspace
# workflow 32461392530 on 2026-08-21. This is a Public + PKCE client, so
# neither the browser nor the API holds a client secret.
mystira_oidc_issuer   = "https://identity.mystira.app/"
mystira_oidc_audience = "celladore-xtox"
# mystira_oidc_encryption_key is a duplicate of Identity's oidc-encryption-key
# (mys-prod-identity-kv). For direct Terraform runs, supply via
# TF_VAR_mystira_oidc_encryption_key; for GitHub Actions, supplied via secret
# TF_VAR_MYSTIRA_OIDC_ENCRYPTION_KEY — never commit the value. Required to decrypt JWE
# access tokens (ADR-0029); not a client secret.
# ConvoLens tokens remain rejected unless Identity has granted and emitted the
# dedicated scope below. This does not broaden any other XtOX endpoint.
mystira_oidc_delegated_audiences = "neuralliquid-convolens-web"
mystira_oidc_transcription_scope = "xtox.transcribe"

api_custom_domain        = "api.xtox.celladoresystems.com"
enable_api_custom_domain = true

# Sluice's transcription passthrough (backend/services/transcription_service.py,
# Baton task 833d6a98). sluice_base_url is not a secret; sluice_api_key is
# supplied via TF_VAR_sluice_api_key (CI secret) and intentionally absent here.
# Model name must be "foundry-whisper", not a bare "whisper" — that's the only
# alias sluice's LiteLLM config registers for the Foundry Whisper deployment
# (infra/modules/sluice_aca/main.tf in celladore/sluice), and the xtox virtual
# key's model allowlist (celladore/sluice scripts/keys.yaml) only permits it.
#
# celladoresystems.com, NOT phoenixvc.tech (was wrong here before this fix).
# Sluice runs two parallel prod stacks during its celladore-sub migration
# (docs/celladore-sub-migration-plan.md): ../prod (bb4e3882 subscription,
# litellm.sluice.phoenixvc.tech, its own pvc-prod-sluice-foundry Whisper
# deployment) and ../prod-celladore (614e6f86 = celladore-sub, THIS
# subscription — see subscription_id's validation above — with its own
# cel-prod-sluice-foundry Whisper deployment and gateway_public_url =
# https://litellm.sluice.celladoresystems.com in that stack's own
# terraform.tfvars). Both register the same "foundry-whisper" alias, so
# using the wrong one wouldn't fail loudly with a 404 — it would silently
# call the wrong subscription's Foundry deployment. xtox itself is pinned
# to celladore-sub and every other domain in this file (allowed_origins,
# swa_custom_domain) already uses celladoresystems.com; sluice_base_url was
# the one value that didn't match, most likely copied from an older
# reference before the celladore-sub stack existed.
sluice_base_url            = "https://litellm.sluice.celladoresystems.com"
sluice_transcription_model = "foundry-whisper"

cosmos_free_tier_enabled = true
cosmos_consistency_level = "Session"

# Rotate before expiration; alerting/rotation job must reference this. See
# sluice's ops runbook pattern (infra/env/prod/terraform.tfvars there).
secrets_expiration_date = "2027-08-20T00:00:00Z"

swa_custom_domain = "xtox.celladoresystems.com"
# DNS prerequisites were applied by celladore/celladore-org run 32461099137:
# the frontend/API CNAMEs and API asuid verification TXT now resolve publicly.
enable_swa_custom_domain = true
