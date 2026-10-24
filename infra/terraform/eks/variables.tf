variable "aws_region" { type = string }
variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Set the intended 12-digit AWS account ID."
  }
}
variable "project" {
  type    = string
  default = "practical-mlops-lab"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,39}$", var.project))
    error_message = "Use a short lowercase project name."
  }
}
variable "kubernetes_version" { type = string }
variable "admin_principal_arn" { type = string }
variable "api_access_cidrs" {
  type = list(string)
  validation {
    condition     = length(var.api_access_cidrs) > 0 && alltrue([for cidr in var.api_access_cidrs : can(cidrhost(cidr, 0)) && !contains(["0.0.0.0/0", "::/0"], cidr)])
    error_message = "Set restricted API access CIDRs, such as your public IP /32."
  }
}
variable "node_instance_type" {
  type    = string
  default = "m7i.xlarge"
}
