provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.account_id]
  default_tags {
    tags = { LabProject = var.project, ManagedBy = "terraform", Lifecycle = "ephemeral" }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

module "vpc" {
  source                  = "terraform-aws-modules/vpc/aws"
  version                 = "6.7.3"
  name                    = var.project
  cidr                    = "10.82.0.0/16"
  azs                     = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets          = ["10.82.0.0/24", "10.82.1.0/24"]
  map_public_ip_on_launch = true
  enable_nat_gateway      = false
  enable_dns_hostnames    = true
  public_subnet_tags      = { "kubernetes.io/role/elb" = "1" }
}

module "eks" {
  source                                 = "terraform-aws-modules/eks/aws"
  version                                = "21.29.0"
  name                                   = var.project
  kubernetes_version                     = var.kubernetes_version
  vpc_id                                 = module.vpc.vpc_id
  subnet_ids                             = module.vpc.public_subnets
  endpoint_private_access                = true
  endpoint_public_access                 = true
  endpoint_public_access_cidrs           = var.api_access_cidrs
  create_kms_key                         = false
  encryption_config                      = null
  cloudwatch_log_group_retention_in_days = 1
  addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = { before_compute = true }
    eks-pod-identity-agent = { before_compute = true }
    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }
  access_entries = {
    lab_admin = {
      principal_arn = var.admin_principal_arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }
  eks_managed_node_groups = {
    lab = {
      use_custom_launch_template = false
      capacity_type              = "ON_DEMAND"
      instance_types             = [var.node_instance_type]
      ami_type                   = "AL2023_x86_64_STANDARD"
      min_size                   = 1
      max_size                   = 1
      desired_size               = 1
      disk_size                  = 40
    }
  }
}
