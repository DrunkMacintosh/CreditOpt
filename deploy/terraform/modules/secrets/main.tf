variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Explicit region for user-managed secret replication."
  type        = string
}

variable "secret_ids" {
  description = "Secret Manager container IDs. Payloads and versions are provisioned out of band."
  type        = set(string)
}

resource "google_secret_manager_secret" "runtime" {
  for_each = var.secret_ids

  project   = var.project_id
  secret_id = each.value

  labels = {
    data_class = "synthetic"
    managed_by = "terraform"
  }

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "secret_ids" {
  description = "Created secret container IDs."
  value       = { for name, secret in google_secret_manager_secret.runtime : name => secret.secret_id }
}
