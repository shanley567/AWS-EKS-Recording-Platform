module "eks" {

  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  # EKS cluster configuration.
  name               = "radio-platform"
  kubernetes_version = "1.34"

  # AWS-managed cluster add-ons.
  addons = {

    # AWS VPC CNI plugin.
    # Must be installed before worker nodes.
    vpc-cni = {
      before_compute = true
      addon_version  = "v1.22.4-eksbuild.14"
    }

    # Kubernetes network proxy.
    kube-proxy = {
      addon_version = "v1.34.6-eksbuild.69"
    }

    # Cluster DNS.
    coredns = {
      addon_version = "v1.12.4-eksbuild.82"
    }

    # EBS CSI Driver.
    #
    # Enables dynamic provisioning of EBS-backed
    # Persistent Volumes through PersistentVolumeClaims.
    #
    # Uses IRSA for AWS API access.
    
    aws-ebs-csi-driver = {
      service_account_role_arn = aws_iam_role.ebs_csi_driver.arn
    }
  }

  # Grant cluster creator admin permissions.
  enable_cluster_creator_admin_permissions = true

  # Public API endpoint.
  endpoint_public_access = true

  # Networking.
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Managed node group.
  eks_managed_node_groups = {

    default = {

      instance_types = [
        "t3.small"
      ]

      capacity_type = "ON_DEMAND"

      min_size     = 1
      max_size     = 2
      desired_size = 2 
    }
  }
}