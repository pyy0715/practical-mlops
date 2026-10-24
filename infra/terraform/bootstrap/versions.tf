terraform {
  required_version = ">= 1.14.0, < 2.0.0"
  backend "local" {}
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "3.3.0"
    }
  }
}
