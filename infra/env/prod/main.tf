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
  subscription_id = var.subscription_id
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

  cosmos_free_tier_enabled = var.cosmos_free_tier_enabled
  cosmos_consistency_level = var.cosmos_consistency_level
  secrets_expiration_date  = var.secrets_expiration_date

  swa_custom_domain        = var.swa_custom_domain
  enable_swa_custom_domain = var.enable_swa_custom_domain
}

# Adopt the Container App Azure actually created during the first real
# apply (before PR #12's GHCR-credential fix). ARM created the resource
# shell, then the platform's image-pull step failed with UNAUTHORIZED
# (private ghcr.io/celladore/xtox-api, no registry credentials configured
# yet) — Terraform's create never got a clean return and so never wrote an
# ID to state, but the ARM resource itself was left behind. The next apply
# (after PR #12/#13) then hit "a resource with this ID already exists" on
# module.xtox.azurerm_container_app.ca. Same class of gap already
# documented for sluice's SWA custom-domain import (see
# celladore/sluice's infra/env/prod-celladore/main.tf) — a Create that
# partially succeeds in Azure but fails before Terraform records the ID.
# Importing (a Read) picks up the existing shell; the apply right after
# this reconciles it to the desired config (image digest, registry
# credentials, sluice_base_url) via a normal in-place update, not a
# destroy/recreate.
import {
  to = module.xtox.azurerm_container_app.ca
  id = "/subscriptions/614e6f86-e401-4bdf-8479-a59986e18815/resourceGroups/cel-prod-xtox-rg/providers/Microsoft.App/containerApps/cel-prod-xtox-ca"
}

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
