variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region for all resources"
}

variable "environment" {
  type        = string
  description = "Environment name: staging or production"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Must be 'staging' or 'production'."
  }
}

variable "image_tag" {
  type        = string
  description = "Docker image tag to deploy (e.g. sha-abc1234)"
}

variable "github_repository" {
  type        = string
  description = "GitHub repository in 'owner/repo' format"
}

variable "secret_key" {
  type        = string
  sensitive   = true
  description = "JWT signing key — injected from Secret Manager, never in state"
}

variable "db_tier" {
  type        = string
  default     = "db-f1-micro"
  description = "Cloud SQL machine tier. Use db-f1-micro for staging, db-n1-standard-1 for production."
}

variable "min_instances" {
  type        = number
  default     = 0
  description = "Minimum Cloud Run instances. 0 = scale to zero (staging). 1+ = always-on (production)."
}

variable "max_instances" {
  type        = number
  default     = 10
  description = "Maximum Cloud Run instances for autoscaling."
}
