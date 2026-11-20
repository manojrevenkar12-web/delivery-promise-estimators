output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "workload_client_id" {
  value       = azurerm_user_assigned_identity.workload.client_id
  description = "Put this in the service accounts' azure.workload.identity/client-id annotation."
}

output "storage_account" {
  value = azurerm_storage_account.this.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}
