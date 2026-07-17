variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "api_secret_ids" {
  description = "Secret IDs readable only by the API runtime identity."
  type        = set(string)
}

variable "worker_secret_ids" {
  description = "Secret IDs readable only by the worker runtime identity."
  type        = set(string)
}

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "creditops-api"
  display_name = "CreditOps API runtime"
  description  = "Runtime identity for the authenticated Cloud Run API."
}

resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "creditops-worker"
  display_name = "CreditOps worker runtime"
  description  = "Runtime identity for the private one-task Cloud Run Job."
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "creditops-scheduler"
  display_name = "CreditOps recovery scheduler"
  description  = "Identity used only to request recovery-sweep Job executions."
}

resource "google_secret_manager_secret_iam_member" "api" {
  for_each = var.api_secret_ids

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "worker" {
  for_each = var.worker_secret_ids

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

output "api_service_account_email" {
  value = google_service_account.api.email
}

output "worker_service_account_email" {
  value = google_service_account.worker.email
}

output "scheduler_service_account_email" {
  value = google_service_account.scheduler.email
}
