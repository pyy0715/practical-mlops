data "terraform_remote_state" "eks" {
  backend = "local"
  config = {
    path = abspath("${path.module}/../../../.local/eks.tfstate")
  }
}
locals {
  cluster = data.terraform_remote_state.eks.outputs
}

provider "helm" {
  kubernetes = {
    host                   = local.cluster.cluster_endpoint
    cluster_ca_certificate = base64decode(local.cluster.cluster_certificate_authority_data)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", local.cluster.cluster_name, "--region", local.cluster.aws_region]
    }
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.11.1"
  timeout          = 900
  values           = [file("${path.module}/../../../apps/addons/argocd/values.yaml")]
}

resource "helm_release" "bridge" {
  name      = "gitops-bridge"
  namespace = "argocd"
  chart     = "${path.module}/../../../apps/argocd/bootstrap"
  timeout   = 300
  values = [yamlencode({
    project        = local.cluster.project
    clusterName    = local.cluster.cluster_name
    region         = local.cluster.aws_region
    gitopsRepoUrl  = var.gitops_repo_url
    gitopsRevision = var.gitops_revision
  })]
  depends_on = [helm_release.argocd]
}
