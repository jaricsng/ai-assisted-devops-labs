variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  default     = "asia-southeast1"
  description = "GCP region"
}

variable "image_tag" {
  type        = string
  description = "Docker image tag to deploy — injected by CI (e.g. sha-abc1234)"
}

variable "github_repository" {
  type        = string
  description = "GitHub repository in 'owner/repo' format"
}

variable "secret_key" {
  type        = string
  sensitive   = true
  description = "JWT signing key — injected from CI secrets, never hardcoded"
}
