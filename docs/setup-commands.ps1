$ErrorActionPreference = 'Stop'

# Command 1
Set-Location "C:\Users\js105\Documents\Coding_portfolio\radio-recording-platform\terraform"

###############################################
# Run terraform plan manually first to check for any issues before applying
###############################################

# Command 2
terraform apply

###############################################
# Requires yes to be entered to confirm the apply
###############################################

# Command 3
aws eks update-kubeconfig `
  --region eu-west-2 `
  --name radio-platform

# Command 4
kubectl get nodes

# Command 5
kubectl get pods -n kube-system

# Command 6
aws ecr describe-repositories `
--repository-names synthetic-generator `
--region eu-west-2

# Command 7
aws ecr get-login-password `
--region eu-west-2 |
docker login `
--username AWS `
--password-stdin `
548722508417.dkr.ecr.eu-west-2.amazonaws.com


# Command 8
docker push `
548722508417.dkr.ecr.eu-west-2.amazonaws.com/synthetic-generator:v0.6.2
# Command 9
aws ecr describe-images `
>>   --repository-name synthetic-generator `
>>   --region eu-west-2 `
>> |  Select-String -Pattern '"imageTags"' -Context 0,2

Set-Location "C:\Users\js105\Documents\Coding_portfolio\radio-recording-platform"

# Command 10
kubectl apply -f kubernetes/namespace.yaml
# Command 11
kubectl get ns


# Command 12
kubectl apply -f kubernetes/serviceaccount.yaml

# Command 13
kubectl get sa `
-n radio-platform

# Command 14
kubectl get sa `
synthetic-generator `
-n radio-platform `
-o yaml |
Select-String "role-arn" -Context 0,1

# Command 15
kubectl apply -f kubernetes/deployment.yaml

# Command 16
kubectl rollout status deployment/synthetic-generator `
-n radio-platform

# Command 17
kubectl get pods `
-n radio-platform

# Command 18
kubectl apply -f kubernetes/service.yaml

# Command 19
kubectl get svc `
-n radio-platform `
--show-labels

# Command 20
kubectl logs deployment/synthetic-generator `
-n radio-platform `
--tail=50

## Command 21
# kubectl exec `
# -n radio-platform `
# <pod-name> `
# -- env | findstr AWS

# Command 22
aws s3 ls `
s3://jsp-radio-recordings-bucket-2026-demo/

# Command 23
kubectl create namespace monitoring

# Command 24
helm repo add prometheus-community `
https://prometheus-community.github.io/helm-charts

# Command 25
helm repo update

# Command 26
helm install monitoring `
prometheus-community/kube-prometheus-stack `
-n monitoring

###############################################
# Sleep required
###############################################

# Command 27
kubectl apply `
-f observability/servicemonitor.yaml

# Command 28
kubectl apply `
-f observability/prometheus-rules.yaml

# Command 29
kubectl get prometheusrules `
-n monitoring

# Command 30
kubectl get prometheusrule `
radio-platform-alerts `
-n monitoring `
--show-labels

#############################################
# Verify promethius to ports
#############################################

#############################################
# Verify Grafana to ports
#############################################

#############################################
# Verify Health endpoints
#############################################

# Command 31
[System.Text.Encoding]::UTF8.GetString(
[System.Convert]::FromBase64String(
(kubectl get secret `
-n monitoring `
monitoring-grafana `
-o jsonpath="{.data.admin-password}")
))

Write-Host "Setup complete."
