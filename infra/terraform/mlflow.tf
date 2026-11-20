# MLflow's backend store: tracking runs and the model registry with its `champion` alias.
resource "random_password" "mlflow" {
  length  = 32
  special = false
}

resource "azurerm_postgresql_flexible_server" "mlflow" {
  name                          = "${var.prefix}-mlflow-${random_string.suffix.result}"
  resource_group_name           = azurerm_resource_group.this.name
  location                      = azurerm_resource_group.this.location
  version                       = "16"
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  administrator_login           = "mlflow"
  administrator_password        = random_password.mlflow.result
  public_network_access_enabled = false
  zone                          = "1"
  tags                          = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "mlflow" {
  name      = "mlflow"
  server_id = azurerm_postgresql_flexible_server.mlflow.id
}

resource "azurerm_key_vault" "this" {
  name                       = "${var.prefix}-kv-${random_string.suffix.result}"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = true
  tags                       = local.tags
}

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault_secret" "mlflow_db" {
  name         = "mlflow-db-uri"
  key_vault_id = azurerm_key_vault.this.id
  value        = "postgresql://mlflow:${random_password.mlflow.result}@${azurerm_postgresql_flexible_server.mlflow.fqdn}:5432/mlflow?sslmode=require"
}

resource "azurerm_role_assignment" "kv_reader" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
}

resource "azurerm_consumption_budget_resource_group" "this" {
  name              = "${var.prefix}-budget"
  resource_group_id = azurerm_resource_group.this.id
  amount            = var.monthly_budget_eur
  time_grain        = "Monthly"
  time_period {
    start_date = "2026-12-01T00:00:00Z"
  }
  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_roles  = ["Owner"]
    contact_emails = var.budget_contact_emails
  }
  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_roles  = ["Owner"]
    contact_emails = var.budget_contact_emails
  }
}
