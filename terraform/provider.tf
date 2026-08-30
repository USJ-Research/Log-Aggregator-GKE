terraform {
  backend "gcs" {
    bucket      = "uni-research-log-bucket"
    prefix      = "terraform/state"
    credentials = "key.json"
  }
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.33.0"
    }
  }
}

provider "google" {
  project     = var.project_id
  credentials = "key.json"
}