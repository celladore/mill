terraform {
  required_version = ">= 1.14.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.62.0, < 5.0.0"
    }
  }

  # Backend config (storage account/container/key) is supplied via
  # `-backend-config` at init time (CI) rather than hardcoded here, matching
  # sluice's infra/env/prod convention.
  backend "azurerm" {}
}

# subscription_id is pinned explicitly here rather than left to inherit the
# az CLI's ambient/default subscription. Confirmed 2026-08-20 that the CLI's
# active-account pointer is not stable in this shared environment — it
# flipped from celladore-sub to sluice's separate bb4e3882 prod subscription
# mid-session with no `az account set` issued. The AzureRM provider does not
# read the CLI's active-account pointer at all (it uses this block /
# ARM_SUBSCRIPTION_ID), so this pin is what actually closes that gap for
# `terraform plan`/`apply` — sluice's own provider block does not do this and
# should not be copied as a counter-example.
provider "azurerm" {
  features {}
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

module "xtox" {
  source = "../../modules/xtox_api_aca"

  env      = var.env
  projname = var.projname
  location = var.location
  tags     = var.tags

  swa_location = var.swa_location

  container_image             = var.container_image
  container_registry_username = var.container_registry_username
  container_registry_password = var.container_registry_password

  min_replicas   = var.min_replicas
  max_replicas   = var.max_replicas
  container_port = var.container_port

  db_name                    = var.db_name
  allowed_origins            = var.allowed_origins
  sluice_base_url            = var.sluice_base_url
  sluice_api_key             = var.sluice_api_key
  sluice_transcription_model = var.sluice_transcription_model

  mystira_oidc_issuer              = var.mystira_oidc_issuer
  mystira_oidc_audience            = var.mystira_oidc_audience
  mystira_oidc_encryption_key      = var.mystira_oidc_encryption_key
  mystira_oidc_delegated_audiences = var.mystira_oidc_delegated_audiences
  mystira_oidc_transcription_scope = var.mystira_oidc_transcription_scope

  api_custom_domain        = var.api_custom_domain
  enable_api_custom_domain = var.enable_api_custom_domain

  cosmos_free_tier_enabled = var.cosmos_free_tier_enabled
  cosmos_consistency_level = var.cosmos_consistency_level
  secrets_expiration_date  = var.secrets_expiration_date

  swa_custom_domain        = var.swa_custom_domain
  enable_swa_custom_domain = var.enable_swa_custom_domain
}

# The 2026-08-21 production apply created both resources in Azure before the
# provider could write them to state. The storage-account create then failed
# its data-plane readiness poll because the provider was still using Shared
# Key, while the SWA custom-domain create completed in Azure but its
# subscription-scoped operation-status poll was denied. Adopt the completed
# resources so the recovery apply updates them instead of attempting duplicate
# creates. These imports are idempotent once the resources are in state.
import {
  to = module.xtox.azurerm_storage_account.documents
  id = "/subscriptions/614e6f86-e401-4bdf-8479-a59986e18815/resourceGroups/cel-prod-xtox-rg/providers/Microsoft.Storage/storageAccounts/celprodxtoxdocs"
}

# NOTE (2026-08-26): the SWA custom-domain import block that lived here
# adopted the pre-cutover xtox.celladoresystems.com binding
# (customDomains/xtox.celladoresystems.com). That Azure object no longer
# exists — the hard cutover to mill.celladoresystems.com destroyed it — so
# the import failed plan-time with "Cannot import non-existent remote
# object" (broke PR #34's terraform-plan). Confirmed via
# `az resource show` that no mill.celladoresystems.com custom domain object
# exists yet either, so per this block's own prior note ("safe to delete
# once the mill binding is the one in state") it's deleted outright rather
# than retargeted: terraform plan will now show
# azurerm_static_web_app_custom_domain.xtox[0] as a plain create.

# NOTE: this stack briefly carried an `import` block here to adopt the
# Container App orphaned by the first real apply (before PR #12's
# GHCR-credential fix — ARM created the resource shell, then the
# platform's image-pull step failed UNAUTHORIZED before Terraform wrote an
# ID to state). That import was reverted: the orphaned resource was not
# just missing from state, its ARM ProvisioningState was itself 'Failed'
# (confirmed via `az containerapp show`: registries: null on the private
# ghcr.io/celladore/xtox-api image — created before any registry
# credentials existed). Azure refuses `listSecrets` on a Container App in
# ProvisioningState 'Failed' (400 ResourceNotProvisioned), which blocks
# even Terraform's plan-time refresh of an imported resource — the
# `az containerapp env show` check confirmed the environment itself is
# healthy (Succeeded), so the app alone was the broken piece. The resource
# was deleted directly in Azure (never held real state — no revision ever
# ran) so this module's azurerm_container_app.ca now does a plain create
# against a clean slate, with GHCR credentials and the correct
# sluice_base_url already wired in from PR #12/#13. Contrast with sluice's
# own SWA custom-domain import (celladore/sluice's
# infra/env/prod-celladore/main.tf), which stays an import because that
# resource actually finished provisioning successfully in Azure — only
# Terraform's state was missing the ID, not the resource's own health.

output "api_fqdn" {
  value = module.xtox.api_fqdn
}

output "swa_default_hostname" {
  value = module.xtox.swa_default_hostname
}

output "swa_api_key" {
  value     = module.xtox.swa_api_key
  sensitive = true
}

output "cosmos_account_name" {
  value = module.xtox.cosmos_account_name
}

output "document_storage_account_name" {
  value = module.xtox.document_storage_account_name
}
