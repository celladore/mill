output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.cae.id
}

output "key_vault_id" {
  value = azurerm_key_vault.kv.id
}

output "api_fqdn" {
  description = "Default *.azurecontainerapps.io hostname for the xtox API. No custom domain is bound for the API — only the SWA frontend has one (var.swa_custom_domain)."
  value       = azurerm_container_app.ca.latest_revision_fqdn
}

output "cosmos_account_name" {
  value = azurerm_cosmosdb_account.mongo.name
}

output "swa_default_hostname" {
  description = "Default *.azurestaticapps.net hostname for the SWA. Point var.swa_custom_domain's CNAME at this (from celladore-org's DNS stack) before flipping enable_swa_custom_domain to true."
  value       = azurerm_static_web_app.swa.default_host_name
}

output "swa_api_key" {
  description = "Deployment token for the SWA — consumed by Azure/static-web-apps-deploy in CI. Sensitive; store as a GitHub Actions secret, not in tfvars."
  value       = azurerm_static_web_app.swa.api_key
  sensitive   = true
}
