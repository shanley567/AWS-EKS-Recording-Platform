# --------------------------------------------------
# Shared values
# --------------------------------------------------

locals {

  # OIDC issuer URL used by IRSA trust policies.
  oidc_provider_url = replace(
    module.eks.cluster_oidc_issuer_url,
    "https://",
    ""
  )
}

# --------------------------------------------------
# Generator S3 Upload Policy
#
# Allows the synthetic generator to upload
# recordings into the S3 bucket.
# --------------------------------------------------

resource "aws_iam_policy" "generator_s3_upload" {

  name = "RadioPlatformS3UploadPolicy"

  policy = jsonencode({

    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]

        Resource = "${aws_s3_bucket.recordings.arn}/*"
      }
    ]
  })
}

# --------------------------------------------------
# Generator IRSA Trust Policy
#
# Allows the Kubernetes service account:
#
# radio-platform/synthetic-generator
#
# to assume this IAM role using OIDC.
# --------------------------------------------------

data "aws_iam_policy_document" "generator_assume_role" {

  statement {

    effect = "Allow"

    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]

    principals {

      type = "Federated"

      identifiers = [
        module.eks.oidc_provider_arn
      ]
    }

    condition {

      test = "StringEquals"

      variable = "${local.oidc_provider_url}:sub"

      values = [
        "system:serviceaccount:radio-platform:synthetic-generator"
      ]
    }
  }
}

# --------------------------------------------------
# Generator IAM Role
#
# Assumed by the synthetic generator pod
# through IRSA.
# --------------------------------------------------

resource "aws_iam_role" "generator" {

  name = "radio-platform-generator"

  assume_role_policy = data.aws_iam_policy_document.generator_assume_role.json
}

# --------------------------------------------------
# Attach S3 Upload Policy
# --------------------------------------------------

resource "aws_iam_role_policy_attachment" "generator_s3" {

  role = aws_iam_role.generator.name

  policy_arn = aws_iam_policy.generator_s3_upload.arn
}

# --------------------------------------------------
# EBS CSI Driver IRSA Trust Policy
#
# Allows:
#
# kube-system/ebs-csi-controller-sa
#
# to assume an AWS IAM role and provision
# EBS volumes on behalf of Kubernetes.
# --------------------------------------------------

data "aws_iam_policy_document" "ebs_csi_assume_role" {

  statement {

    effect = "Allow"

    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]

    principals {

      type = "Federated"

      identifiers = [
        module.eks.oidc_provider_arn
      ]
    }

    condition {

      test = "StringEquals"

      variable = "${local.oidc_provider_url}:sub"

      values = [
        "system:serviceaccount:kube-system:ebs-csi-controller-sa"
      ]
    }
  }
}

# --------------------------------------------------
# EBS CSI Driver IAM Role
#
# Used by the AWS EBS CSI controller to:
#
# - Create EBS volumes
# - Attach volumes to nodes
# - Detach volumes
# - Delete volumes
#
# Required for Kubernetes PVC support.
# --------------------------------------------------

resource "aws_iam_role" "ebs_csi_driver" {

  name = "radio-platform-ebs-csi-driver"

  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume_role.json
}

# --------------------------------------------------
# Attach AWS Managed EBS CSI Policy
#
# AWS-managed policy granting required
# EBS permissions.
# --------------------------------------------------

resource "aws_iam_role_policy_attachment" "ebs_csi" {

  role = aws_iam_role.ebs_csi_driver.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}