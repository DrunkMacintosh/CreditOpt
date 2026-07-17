terraform {
  required_version = ">= 1.10.0, < 2.0.0"
}

# CONFIRMED: this environment accepts synthetic data only.
# OPEN QUESTION: approved regions, resource sizing, timeouts, identity integration,
# provider endpoints, notification channels, and production-data authorization.

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "container_image" {
  type = string
}

variable "api_cpu" {
  type = string
}

variable "api_memory" {
  type = string
}

variable "api_timeout_seconds" {
  type = number
}

variable "api_concurrency" {
  type = number
}

variable "api_min_instances" {
  type = number
}

variable "api_max_instances" {
  type = number
}

variable "worker_cpu" {
  type = string
}

variable "worker_memory" {
  type = string
}

variable "worker_timeout_seconds" {
  type = number
}

variable "api_secret_refs" {
  description = "Secret IDs and pinned numeric versions only. Never put secret values in tfvars."
  type = map(object({
    secret_id = string
    version   = string
  }))
}

variable "worker_secret_refs" {
  description = "Secret IDs and pinned numeric versions only. Never put secret values in tfvars."
  type = map(object({
    secret_id = string
    version   = string
  }))
}

variable "notification_channel_ids" {
  type    = list(string)
  default = []
}

module "creditops_dev" {
  source = "../.."

  project_id               = var.project_id
  region                   = var.region
  container_image          = var.container_image
  app_env                  = "development"
  data_class               = "synthetic"
  api_cpu                  = var.api_cpu
  api_memory               = var.api_memory
  api_timeout_seconds      = var.api_timeout_seconds
  api_concurrency          = var.api_concurrency
  api_min_instances        = var.api_min_instances
  api_max_instances        = var.api_max_instances
  worker_cpu               = var.worker_cpu
  worker_memory            = var.worker_memory
  worker_timeout_seconds   = var.worker_timeout_seconds
  api_secret_refs          = var.api_secret_refs
  worker_secret_refs       = var.worker_secret_refs
  notification_channel_ids = var.notification_channel_ids
}

output "api_url" {
  value = module.creditops_dev.api_url
}

output "worker_job_name" {
  value = module.creditops_dev.worker_job_name
}
