variable "subscription_id" {
  type        = string
  description = "Azure subscription to deploy into."
}

variable "location" {
  type    = string
  default = "germanywestcentral"
}

variable "prefix" {
  type    = string
  default = "dpe"
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "monthly_budget_eur" {
  type    = number
  default = 1500
}

variable "budget_contact_emails" {
  type    = list(string)
  default = []
}
