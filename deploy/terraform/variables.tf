variable "project_id" {
  description = "Google Cloud project ID for this synthetic development environment."
  type        = string
}

variable "region" {
  description = "Approved Google Cloud region. Data residency remains an open release gate."
  type        = string
}

variable "container_image" {
  description = "Immutable API/worker image reference, preferably pinned by digest."
  type        = string

  validation {
    condition     = strcontains(var.container_image, "@sha256:")
    error_message = "container_image must be pinned by sha256 digest."
  }
}

variable "app_env" {
  description = "Application environment; this definition is restricted to synthetic development."
  type        = string
  default     = "development"

  validation {
    condition     = var.app_env == "development"
    error_message = "Only the development environment is defined by this unapproved infrastructure."
  }
}

variable "data_class" {
  description = "Authorized data class. Real banking data is prohibited."
  type        = string
  default     = "synthetic"

  validation {
    condition     = var.data_class == "synthetic"
    error_message = "Only synthetic data is authorized."
  }
}

variable "api_cpu" {
  description = "Cloud Run API CPU limit, explicitly selected for the environment."
  type        = string
}

variable "api_memory" {
  description = "Cloud Run API memory limit, explicitly selected for the environment."
  type        = string
}

variable "api_timeout_seconds" {
  description = "Cloud Run API request timeout in seconds."
  type        = number
}

variable "api_concurrency" {
  description = "Maximum concurrent requests per API instance."
  type        = number
}

variable "api_min_instances" {
  description = "Minimum API instances."
  type        = number
}

variable "api_max_instances" {
  description = "Maximum API instances."
  type        = number
}

variable "worker_cpu" {
  description = "Cloud Run worker CPU limit, explicitly selected for the environment."
  type        = string
}

variable "worker_memory" {
  description = "Cloud Run worker memory limit, explicitly selected for the environment."
  type        = string
}

variable "worker_timeout_seconds" {
  description = "Maximum duration of one worker task in seconds."
  type        = number
}

variable "scheduler_schedule" {
  description = "Recovery-sweep cron schedule."
  type        = string
  default     = "* * * * *"
}

variable "scheduler_time_zone" {
  description = "Recovery-sweep cron time zone."
  type        = string
  default     = "Etc/UTC"
}

variable "api_secret_refs" {
  description = "API environment names mapped to Secret Manager IDs and numeric pinned versions. No payloads."
  type = map(object({
    secret_id = string
    version   = string
  }))

  validation {
    condition = alltrue([
      for ref in values(var.api_secret_refs) : can(regex("^[1-9][0-9]*$", ref.version))
    ])
    error_message = "Every API secret reference must use a positive numeric version, never latest."
  }
}

variable "worker_secret_refs" {
  description = "Worker environment names mapped to Secret Manager IDs and numeric pinned versions. No payloads."
  type = map(object({
    secret_id = string
    version   = string
  }))

  validation {
    condition = alltrue([
      for ref in values(var.worker_secret_refs) : can(regex("^[1-9][0-9]*$", ref.version))
    ])
    error_message = "Every worker secret reference must use a positive numeric version, never latest."
  }
}

variable "notification_channel_ids" {
  description = "Pre-existing Monitoring notification channel resource IDs."
  type        = list(string)
  default     = []
}

variable "manual_review_growth_threshold" {
  description = "Synthetic-dev manual-review event rate alert threshold per second."
  type        = number
  default     = 0.1
}

variable "dispatch_failure_threshold" {
  description = "Synthetic-dev dispatch failure event rate alert threshold per second."
  type        = number
  default     = 0
}

variable "queue_age_threshold_seconds" {
  description = "Synthetic-dev oldest eligible queue item age alert threshold."
  type        = number
  default     = 300
}

variable "provider_failure_rate_threshold" {
  description = "Synthetic-dev provider failure event rate alert threshold per second."
  type        = number
  default     = 0.01
}
