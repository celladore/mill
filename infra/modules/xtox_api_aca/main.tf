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

resource "azurerm_key_vault_secret" "mystira_oidc_encryption_key" {
  count           = var.mystira_oidc_encryption_key != "" ? 1 : 0
  name            = "mystira-oidc-encryption-key"
  value           = var.mystira_oidc_encryption_key
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

resource "azurerm_storage_container" "artifacts" {
  name                  = "artifacts"
  storage_account_id    = azurerm_storage_account.documents.id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "artifacts" {
  storage_account_id = azurerm_storage_account.documents.id

  rule {
    name    = "expire-conversion-artifacts"
    enabled = true
    filters {
      prefix_match = ["${azurerm_storage_container.artifacts.name}/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = var.artifact_retention_days
      }
    }
  }
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
    for_each = azurerm_key_vault_secret.mystira_oidc_encryption_key
    content {
      name                = "mystira-oidc-encryption-key"
      key_vault_secret_id = secret.value.versionless_id
      identity            = azurerm_user_assigned_identity.ca.id
    }
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
        name  = "AZURE_ARTIFACT_CONTAINER"
        value = azurerm_storage_container.artifacts.name
      }
      env {
        name  = "CONVERSION_RETENTION_SECONDS"
        value = tostring(var.artifact_retention_days * 86400)
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
      dynamic "env" {
        for_each = azurerm_key_vault_secret.mystira_oidc_encryption_key
        content {
          name        = "MYSTIRA_OIDC_ENCRYPTION_KEY"
          secret_name = "mystira-oidc-encryption-key"
        }
      }
      env {
        name  = "MYSTIRA_OIDC_DELEGATED_AUDIENCES"
        value = var.mystira_oidc_delegated_audiences
      }
      env {
        name  = "MYSTIRA_OIDC_TRANSCRIPTION_SCOPE"
        value = var.mystira_oidc_transcription_scope
      }
      env {
        name  = "MYSTIRA_OIDC_RENDER_AUDIENCES"
        value = var.mystira_oidc_render_audiences
      }
      env {
        name  = "MYSTIRA_OIDC_RENDER_SCOPE"
        value = var.mystira_oidc_render_scope
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
  # for_each (not count) — see the incident history on the cert resource
  # below, part 3. A hostname cutover needs the old hostname's binding
  # destroyed and the new hostname's binding created as two independent
  # resource instances, never a replace of one fixed `[0]` address.
  for_each         = var.enable_api_custom_domain ? toset([var.api_custom_domain]) : toset([])
  name             = each.value
  container_app_id = azurerm_container_app.ca.id

  lifecycle {
    # container_app_environment_managed_certificate_id is provider-computed
    # (populated by the out-of-band `az containerapp hostname bind` step in
    # deploy.yaml, not by this config) — Terraform flags it as a "redundant
    # ignore_changes element" if listed here, since there's never a
    # configured value on our side to compare against. Only
    # certificate_binding_type is actually ours to ignore.
    ignore_changes = [certificate_binding_type]
  }

  # No depends_on here — see incident history part 4 on the cert resource
  # below. The edge belongs on the cert (cert depends_on domain), not here.
}

resource "azurerm_container_app_environment_managed_certificate" "api" {
  # for_each (not count) — see incident history part 3 below.
  for_each                     = var.enable_api_custom_domain ? toset([var.api_custom_domain]) : toset([])
  name                         = replace(each.value, ".", "-")
  container_app_environment_id = azurerm_container_app_environment.cae.id
  subject_name                 = each.value
  domain_control_validation    = "CNAME"
  tags                         = local.tags

  # ── Incident history: api.xtox.celladoresystems.com -> api.mill.celladoresystems.com (2026-08-26) ──
  #
  # 1. depends_on originally pointed the wrong way (cert -> domain), which is
  #    backwards for a replace: Terraform destroys in the reverse of create
  #    order, so "cert depends on domain" meant the cert was destroyed
  #    BEFORE the domain. Azure refused with a 400 CertificateInUse because
  #    the still-live api.xtox custom domain (bound to this cert via the
  #    out-of-band `az containerapp hostname bind` step in deploy.yaml,
  #    which Terraform doesn't track — see ignore_changes on the domain
  #    resource above) was still referencing it. Fix (780bf10): move
  #    depends_on onto the domain resource instead, so destroy order becomes
  #    domain-first, cert-second — matching what Azure actually requires.
  #
  # 2. That fix alone was incomplete: both resources were still `count`-
  #    indexed (a single `[0]` instance) with the cert's name hardcoded to
  #    "xtox-api-managed". A hostname change force-replaces both at the SAME
  #    address, and the domain's depends_on the cert created a genuine
  #    destroy/destroy cycle once both were being replaced simultaneously.
  #    Attempted fix (9904697): derive the name from the hostname and add
  #    create_before_destroy to the cert only. That traded the destroy/
  #    destroy cycle for a different one — CBD leaves the old cert as a
  #    "deposed" object whose destroy node still carried the pre-780bf10
  #    dependency edge frozen in state, colliding with the live config's
  #    (now-reversed) edge, and pulled azurerm_container_app.ca into the
  #    same cycle via the domain's container_app_id reference to it.
  #
  # 3. Actual fix for the cycle: stop indexing this pair by a fixed
  #    `count = 1`/`[0]` address at all. for_each keyed on the hostname means
  #    a hostname change removes one map key (old host) and adds another
  #    (new host), as two instances that never share an address — nothing
  #    left for Terraform to linearize into a cycle. terraform-plan on PR #34
  #    confirmed this: clean destroy(old)/create(new) plan, no Cycle error.
  #
  # 4. The for_each fix above never revisited whether 780bf10's direction was
  #    even right — it wasn't, for CREATE. The real terraform-apply on PR #34
  #    (run 32974779057) failed with TWO errors simultaneously:
  #      - deleting the old cert: 400 CertificateInUse (domain still bound)
  #      - creating the new cert: 400 RequireCustomHostnameInEnvironment
  #        (the hostname must be a registered custom domain in the
  #        environment BEFORE a managed cert can be issued for it)
  #    Azure requires domain-before-cert on BOTH create and destroy. A single
  #    plain depends_on can't express that: Terraform always reverses the
  #    edge on destroy, so "domain depends_on cert" (780bf10's direction)
  #    gets destroy right and create wrong, and the reverse gets create right
  #    and destroy wrong. There is no direction that satisfies both — this
  #    isn't fixable by flipping the edge again.
  #
  #    Fix: point the edge the other way — cert depends_on domain (below) —
  #    which matches HashiCorp's own documented example for this resource
  #    pair and gets steady-state CREATE right, which is what matters for
  #    every future hostname change from here on.
  #
  #    This does NOT, by itself, cover the destroy side of a hostname change
  #    (or of flipping enable_api_custom_domain to false). Once a hostname's
  #    for_each key is removed from config, its domain+cert instances become
  #    orphans this depends_on no longer wires together at all — Terraform
  #    falls back to whatever ordering is frozen in state from whenever they
  #    were last applied, which is exactly what produced the CertificateInUse
  #    error above even under the (destroy-correct) 780bf10 direction. That
  #    history can't be inspected or trusted from here, so this is a required
  #    runbook step for EVERY future hostname change and for disabling
  #    enable_api_custom_domain, not just the api.xtox -> api.mill cutover
  #    that surfaced it.
  #
  # 5. The obvious-looking fix for #4 — targeted destroys in explicit
  #    domain-then-cert order — DOES NOT WORK. Tried against the real
  #    api.xtox orphans:
  #
  #      terraform apply -destroy -target='module.xtox.azurerm_container_app_custom_domain.api[0]'
  #
  #    `-target` pulls in dependents of the target, not just the target
  #    itself — the plan came back with BOTH resources (2 to destroy, not 1),
  #    and Terraform executed the cert first anyway, per the same
  #    state-frozen ordering #4 describes. Targeting the cert alone instead
  #    fails identically, for the same reason. There is no `-target`
  #    sequence that produces domain-first: whichever address you target
  #    the other is pulled in, and destroy order still follows the frozen
  #    graph. Do not retry variations of this — the actual runbook step is
  #    to bypass Terraform for the teardown and reconcile state afterward:
  #
  #      az containerapp hostname delete -g <rg> -n <container-app> \
  #        --hostname <old-hostname> --yes
  #      az containerapp env certificate delete -g <rg> -n <container-app-env> \
  #        --certificate <old-cert-name> --yes
  #      terraform state rm 'module.xtox.azurerm_container_app_custom_domain.api["<old-hostname>"]'
  #      terraform state rm 'module.xtox.azurerm_container_app_environment_managed_certificate.api["<old-hostname>"]'
  #
  #    Run in that order — domain unbound before the cert delete (Azure
  #    allows removing the domain while the cert still exists; it refuses to
  #    delete the cert while any domain still references it), then both
  #    `state rm` last so a failed `az` step leaves both addresses intact in
  #    state instead of half-orphaned. (The api.xtox -> api.mill cutover
  #    itself predates the for_each conversion, so its orphans are still
  #    count-indexed: substitute `[0]` for `["<old-hostname>"]` in both
  #    `state rm` commands for that one case only.) Skipping this and just
  #    running a normal apply — targeted or not — risks the same
  #    CertificateInUse failure recurring, since normal apply ordering for
  #    orphaned instances is exactly the state-derived ordering that failed
  #    here.
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

  # Azure does not return validation_type when an existing custom domain is
  # read or imported. Ignore that write-only creation input so adopting a
  # successfully provisioned domain does not force a destructive replacement.
  lifecycle {
    ignore_changes = [validation_type]
  }
}
