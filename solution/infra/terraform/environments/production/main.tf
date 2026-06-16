provider "google" {
  project = var.project_id
  region  = var.region
}

module "task_manager" {
  source = "../../modules/cloud-run"

  project_id        = var.project_id
  region            = var.region
  environment       = "production"
  image_tag         = var.image_tag
  github_repository = var.github_repository
  secret_key        = var.secret_key

  # Production: always-on, higher capacity
  db_tier       = "db-n1-standard-1"
  min_instances = 1
  max_instances = 20
}

output "production_api_url" {
  value = module.task_manager.api_url
}
