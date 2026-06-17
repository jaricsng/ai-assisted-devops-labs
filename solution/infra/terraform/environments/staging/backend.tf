terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "YOUR_PROJECT_ID-terraform-state"
    prefix = "task-manager/staging"
    # State stored at: gs://PROJECT_ID-terraform-state/task-manager/staging/default.tfstate
  }
}
