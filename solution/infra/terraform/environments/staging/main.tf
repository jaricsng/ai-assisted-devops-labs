provider "google" {
  project = var.project_id
  region  = var.region
}

module "task_manager" {
  source = "../../modules/cloud-run"

  project_id        = var.project_id
  region            = var.region
  environment       = "staging"
  image_tag         = var.image_tag
  github_repository = var.github_repository
  secret_key        = var.secret_key

  # Staging: scale to zero to minimise costs
  db_tier       = "db-f1-micro"
  min_instances = 0
  max_instances = 5
}

output "staging_api_url" {
  value = module.task_manager.api_url
}
