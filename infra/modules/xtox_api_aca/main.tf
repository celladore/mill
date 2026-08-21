terraform {
  required_version = ">= 1.14.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.62.0, < 5.0.0"
    }
  }
}

locals {
  # "cel-" prefix per the celladore naming convention — forward-only, applies
  # to new/celladore-owned resources only (confirmed 2026-08-20; does not
  # rename sluice's existing "pvc-" production resources).
  prefix = "cel-${var.env}-${var.projname}"

  rg_name      = "${local.prefix}-rg"
  law_name     = "${local.prefix}-law"
  cae_name     = "${local.prefix}-cae"
  ca_name      = "${local.prefix}-ca"
  cosmos_name  = "${local.prefix}-cosmos"
  swa_name     = "${local.prefix}-swa"
  storage_name = substr("${replace(local.prefix, "-", "")}docs", 0, 24)

  # Key Vault: 3-24 chars, alphanumeric + hyphen, must start with a letter.
  # "cel-prod-xtox-kv" is 16 chars — no truncation needed today, but keep the
  # same guard sluice uses so a longer projname doesn't silently produce an
  # invalid name at apply time instead of a clear plan-time error.
  kv_name_raw = lower(replace("${local.prefix}-kv", "_", "-"))
  kv_name     = substr(try(replace(local.kv_name_raw, regex("^[^a-z]+", local.kv_name_raw), "c"), local.kv_name_raw), 0, 24)

  tags = merge({
    env     = var.env
    project = var.projname
  }, var.tags)
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "rg" {
  name     = local.rg_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = local.law_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_container_app_environment" "cae" {
  name                       = local.cae_name
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
  tags                       = local.tags
}

resource "azurerm_key_vault" "kv" {
  name                = local.kv_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  soft_delete_retention_days = var.env == "prod" ? 30 : 7
  purge_protection_enabled   = var.env == "prod" ? true : false

  tags = local.tags

  network_acls {
    bypass         = "AzureServices"
    default_action = var.key_vault_network_default_action
  }
}

resource "azurerm_key_vault_access_policy" "terraform_client" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge", "Recover"]
}

# ── Cosmos DB for MongoDB (RU-based, free tier) ─────────────────────────────
# API kind is a create-time choice on RU-based accounts, not a per-region
# gate — existing RU-based accounts in celladore-sub already run live in
# southafricanorth (Core-SQL kind); Mongo kind is expected to behave the same
# way, though that has not been empirically apply-tested as of 2026-08-20.
resource "azurerm_cosmosdb_account" "mongo" {
  name                = local.cosmos_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "MongoDB"

  mongo_server_version = "7.0"

  # One free-tier discount per subscription. Confirmed unclaimed in
  # celladore-sub as of 2026-08-20 — see the warning on var.cosmos_free_tier_enabled.
  free_tier_enabled = var.cosmos_free_tier_enabled

  consistency_policy {
    consistency_level = var.cosmos_consistency_level
  }

  # No VNet integration (matches the reasoning sluice uses for its Postgres
  # firewall rule): Container Apps Consumption-plan egress IPs are dynamic,
  # so they can't be allowlisted individually. AzureServices bypass covers
  # first-party Azure callers; anything tighter needs private endpoints.
  is_virtual_network_filter_enabled     = false
  public_network_access_enabled         = true
  network_acl_bypass_for_azure_services = true

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
  }

  capabilities {
    name = "EnableMongo"
  }

  tags = local.tags
}

resource "azurerm_cosmosdb_mongo_database" "xtox" {
  name                = var.db_name
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.mongo.name
  # RU-based, not serverless — matches the account's default throughput mode.
  throughput = 400
}

resource "azurerm_key_vault_secret" "mongo_url" {
  name            = "mongo-url"
  value           = azurerm_cosmosdb_account.mongo.primary_mongodb_connection_string
  key_vault_id    = azurerm_key_vault.kv.id
  expiration_date = var.secrets_expiration_date

  depends_on = [azurerm_key_vault_access_policy.terraform_client]
}

resource "azurerm_key_vault_secret" "sluice_api_key" {
  name            = "sluice-api-key"
  value           = var.sluice_api_key
  key_vault_id    = azurerm_key_vault.kv.id
  expiration_date = var.secrets_expiration_date

  depends_on = [azurerm_key_vault_access_policy.terraform_client]
}

# ── Container App ───────────────────────────────────────────────────────────
resource "azurerm_user_assigned_identity" "ca" {
  name                = "${local.ca_name}-id"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  tags                = local.tags
}

# ── Private document storage ────────────────────────────────────────────────
resource "azurerm_storage_account" "documents" {
  name                            = local.storage_name
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  public_network_access_enabled   = true
  allow_nested_items_to_be_public = false
  tags                            = local.tags

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_id    = azurerm_storage_account.documents.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "document_storage" {
  scope                = azurerm_storage_account.documents.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.ca.principal_id
}

resource "azurerm_key_vault_access_policy" "container_app" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.ca.principal_id

  secret_permissions = ["Get", "List"]
}

resource "azurerm_container_app" "ca" {
  lifecycle {
    precondition {
      condition     = var.min_replicas <= var.max_replicas
      error_message = "min_replicas (${var.min_replicas}) must not exceed max_replicas (${var.max_replicas})."
    }
  }

  depends_on = [azurerm_key_vault_access_policy.container_app]

  name                         = local.ca_name
  container_app_environment_id = azurerm_container_app_environment.cae.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.ca.id]
  }

  secret {
    name                = "mongo-url"
    key_vault_secret_id = azurerm_key_vault_secret.mongo_url.versionless_id
    identity            = azurerm_user_assigned_identity.ca.id
  }

  secret {
    name                = "sluice-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.sluice_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.ca.id
  }

  dynamic "secret" {
    for_each = var.container_registry_password != "" ? [1] : []
    content {
      name  = "ghcr-password"
      value = var.container_registry_password
    }
  }

  dynamic "registry" {
    for_each = var.container_registry_password != "" ? [1] : []
    content {
      server               = "ghcr.io"
      username             = var.container_registry_username
      password_secret_name = "ghcr-password"
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "xtox-api"
      image  = var.container_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "MONGO_URL"
        secret_name = "mongo-url"
      }
      env {
        name  = "DB_NAME"
        value = var.db_name
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "SLUICE_BASE_URL"
        value = var.sluice_base_url
      }
      env {
        name        = "SLUICE_API_KEY"
        secret_name = "sluice-api-key"
      }
      env {
        name  = "SLUICE_TRANSCRIPTION_MODEL"
        value = var.sluice_transcription_model
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = azurerm_storage_account.documents.primary_blob_endpoint
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.documents.name
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.ca.client_id
      }
      env {
        name  = "MYSTIRA_OIDC_ISSUER"
        value = var.mystira_oidc_issuer
      }
      env {
        name  = "MYSTIRA_OIDC_AUDIENCE"
        value = var.mystira_oidc_audience
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/api/"
        port      = var.container_port
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = var.container_port

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

resource "azurerm_container_app_custom_domain" "api" {
  count            = var.enable_api_custom_domain ? 1 : 0
  name             = var.api_custom_domain
  container_app_id = azurerm_container_app.ca.id

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}

resource "azurerm_container_app_environment_managed_certificate" "api" {
  count                        = var.enable_api_custom_domain ? 1 : 0
  name                         = "xtox-api-managed"
  container_app_environment_id = azurerm_container_app_environment.cae.id
  subject_name                 = var.api_custom_domain
  domain_control_validation    = "CNAME"
  tags                         = local.tags

  depends_on = [azurerm_container_app_custom_domain.api]
}

# ── Static Web App (frontend) ───────────────────────────────────────────────
resource "azurerm_static_web_app" "swa" {
  name                = local.swa_name
  location            = var.swa_location
  resource_group_name = azurerm_resource_group.rg.name
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

resource "azurerm_static_web_app_custom_domain" "xtox" {
  count             = var.enable_swa_custom_domain ? 1 : 0
  static_web_app_id = azurerm_static_web_app.swa.id
  domain_name       = var.swa_custom_domain
  # Free-tier SWAs validate custom subdomains via CNAME (confirmed against
  # Microsoft's docs 2026-08-20; TXT-token validation only applies to
  # Enterprise-Grade-Edge / Standard-tier domains). The CNAME itself must
  # already resolve to azurerm_static_web_app.swa.default_host_name before
  # this resource can succeed — see the enable_swa_custom_domain variable.
  validation_type = "cname-delegation"
}
