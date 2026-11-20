resource "azurerm_kubernetes_cluster" "this" {
  name                      = "${var.prefix}-aks"
  location                  = azurerm_resource_group.this.location
  resource_group_name       = azurerm_resource_group.this.name
  dns_prefix                = var.prefix
  kubernetes_version        = var.kubernetes_version
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  sku_tier                  = "Standard"

  default_node_pool {
    name                 = "system"
    vm_size              = "Standard_D4s_v5"
    auto_scaling_enabled = true
    min_count            = 2
    max_count            = 5
    zones                = ["1", "2", "3"]
    upgrade_settings {
      max_surge = "33%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  }

  monitor_metrics {}

  tags = local.tags
}

# The weekly training job runs on its own pool, scaled to zero between runs.
resource "azurerm_kubernetes_cluster_node_pool" "train" {
  name                  = "train"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = "Standard_F8s_v2"
  auto_scaling_enabled  = true
  min_count             = 0
  max_count             = 2
  node_taints           = ["workload=train:NoSchedule"]
  node_labels           = { workload = "train" }
  tags                  = local.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                            = azurerm_container_registry.this.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}

# One identity for the service and the job, federated to their Kubernetes service accounts.
resource "azurerm_user_assigned_identity" "workload" {
  name                = "${var.prefix}-workload"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
}

resource "azurerm_federated_identity_credential" "sa" {
  for_each            = toset(["estimator-api", "train-job"])
  name                = each.key
  resource_group_name = azurerm_resource_group.this.name
  parent_id           = azurerm_user_assigned_identity.workload.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.this.oidc_issuer_url
  subject             = "system:serviceaccount:estimators:${each.key}"
}

resource "azurerm_role_assignment" "blob" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
}
