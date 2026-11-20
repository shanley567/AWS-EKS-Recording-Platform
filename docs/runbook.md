# Radio Recording Platform - Startup Runbook

## Purpose

Rebuild and restore the complete platform after:

- Terraform destroy
- EKS cluster recreation
- Local development environment reset

This runbook restores:

- AWS Infrastructure
- EKS
- Application
- S3 Upload Pipeline
- Prometheus
- Grafana
- Dashboarding
- Health Checks
- Prometheus Alerting

---

# 1. Deploy AWS Infrastructure

From the Terraform directory:

```powershell
terraform init
```

```powershell
terraform plan
```

```powershell
terraform apply
```

Wait until:

```text
Apply complete!
```

---

# 2. Configure kubectl

Update kubeconfig:

```powershell
aws eks update-kubeconfig `
  --region eu-west-2 `
  --name radio-platform
```

Verify connectivity:

```powershell
kubectl get nodes
```

Expected:

```text
STATUS   Ready
```

---

# 3. Verify Core Cluster Components

```powershell
kubectl get pods -n kube-system
```

Expected:

```text
aws-node
coredns
kube-proxy
```

All should be running.

---

# 4. Verify ECR Repository

```powershell
aws ecr describe-repositories `
--repository-names synthetic-generator `
--region eu-west-2
```

Expected:

```text
synthetic-generator
```

---

# 5. Build Application Image

Navigate to:

```powershell
cd app
```

Build latest version:

```powershell
docker build -t <docker_image_version> .
```

Tag:

```powershell
docker tag <docker_image_version> `
548722508417.dkr.ecr.eu-west-2.amazonaws.com/<docker_image_version>
```

---

# 6. Authenticate Docker To ECR

ECR authentication tokens expire regularly.

```powershell
aws ecr get-login-password `
--region eu-west-2 |
docker login `
--username AWS `
--password-stdin `
548722508417.dkr.ecr.eu-west-2.amazonaws.com
```

Expected:

```text
Login Succeeded
```

---

# 7. Push Image

```powershell
docker push `
<tagged_docker_image_version>
```

Expected:

```text
digest: sha256:...
```

Verify Push:

```powershell
aws ecr list-images `
--repository-name synthetic-generator `
--region eu-west-2
```

If image does not show, verification steps:

1. List docker images
2. Re-build
3. Tag Image
4. ECR Auth
5. ECR push

---

# 8. Recreate Application Namespace

```powershell
kubectl apply -f kubernetes/namespace.yaml
```

Verify:

```powershell
kubectl get ns
```

Expected:

```text
radio-platform
```

---

# 9. Recreate Service Account

Required for IRSA authentication.

```powershell
kubectl apply -f kubernetes/serviceaccount.yaml
```

Verify:

```powershell
kubectl get sa `
-n radio-platform
```

Expected:

```text
synthetic-generator
```

Verify IRSA annotation:

```powershell
kubectl get sa `
synthetic-generator `
-n radio-platform `
-o yaml |
Select-String "role-arn" -Context 0,1
```

Expected:

```text
eks.amazonaws.com/role-arn
```

---

# 10. Deploy Application

Verify deployment image:

```yaml
image: 548722508417.dkr.ecr.eu-west-2.amazonaws.com/synthetic-generator:<image_version>
```

Deploy:

```powershell
kubectl apply -f kubernetes/deployment.yaml
```

Monitor rollout:

```powershell
kubectl get pods `
-n radio-platform -w
```

Expected:

```text
1/1 Running
```

Verify rollout completion:

```powershell
kubectl rollout status deployment/synthetic-generator `
-n radio-platform
```

Expected:

```text
successfully rolled out
```

### If rollout fails

Check deployment events:

```powershell
kubectl describe deployment `
synthetic-generator `
-n radio-platform
```

Check pod events:

```powershell
kubectl describe pod <pod-name> `
-n radio-platform |
Select-String "Events:" -Context 0,20
```

Example issue discovered during testing:

```text
FailedScheduling
Too many pods
```

---

# 11. Deploy Service

Ensure Service contains:

```yaml
metadata:
  labels:
    app: synthetic-generator
```

Apply:

```powershell
kubectl apply -f kubernetes/service.yaml
```

Verify:

```powershell
kubectl get svc `
-n radio-platform `
--show-labels
```

Expected:

```text
app=synthetic-generator
```

---

# 12. Verify Application

Check logs:

```powershell
kubectl logs deployment/synthetic-generator `
-n radio-platform `
--tail=50
```

Expected:

```text
Upload successful
```

---

# 13. Verify IRSA Credentials

Verify the pod is using IRSA:

```powershell
kubectl exec `
-n radio-platform `
<pod-name> `
-- env | findstr AWS
```

Expected:

```text
AWS_ROLE_ARN
AWS_WEB_IDENTITY_TOKEN_FILE
AWS_REGION
```

This confirms pod identity is being supplied through IRSA.

---

# 14. Verify S3 Uploads

Verify bucket exists:

```powershell
aws s3 ls
```

Check logs for:

```text
Upload successful
```

Or verify directly:

```powershell
aws s3 ls `
s3://jsp-radio-recordings-bucket-2026-demo `
--recursive
```

Expected:

```text
station-001/...
station-002/...
station-003/...
```

---

# 15. Create Monitoring Namespace

```powershell
kubectl create namespace monitoring
```

If namespace already exists:

```text
Monitoring namespace already exists
```

Continue.

---

# 16. Install kube-prometheus-stack

Add Helm repository:

```powershell
helm repo add prometheus-community `
https://prometheus-community.github.io/helm-charts
```

Update repositories:

```powershell
helm repo update
```

Install monitoring stack:

```powershell
helm install monitoring `
prometheus-community/kube-prometheus-stack `
-n monitoring
```

---

# 17. Wait For Monitoring Components

```powershell
kubectl get pods `
-n monitoring -w
```

Expected:

```text
Grafana

Prometheus

AlertManager

Node Exporter

kube-state-metrics

Prometheus Operator
```

All should become:

```text
Running
```

---

# 18. Deploy ServiceMonitor

Apply:

```powershell
kubectl apply `
-f observability/servicemonitor.yaml
```

Critical label:

```yaml
metadata:
  labels:
    release: monitoring
```

Without this label Prometheus will not discover the ServiceMonitor.

---

# 19. Deploy PrometheusRule Alerts

Apply alert rules:

```powershell
kubectl apply `
-f observability/prometheus-rules.yaml
```

Verify:

```powershell
kubectl get prometheusrules `
-n monitoring
```

Expected:

```text
radio-platform-alerts
```

Verify labels:

```powershell
kubectl get prometheusrule `
radio-platform-alerts `
-n monitoring `
--show-labels
```

Expected:

```text
release=monitoring
```

---

# 20. Verify Prometheus

Port-forward:

```powershell
kubectl port-forward `
-n monitoring `
svc/monitoring-kube-prometheus-prometheus `
9090:9090
```

Open:

```text
http://localhost:9090
```

Run query:

```promql
recordings_generated_total
```

Expected:

```text
station-001

station-002

station-003
```

Verify alert rule group:

```text
Status
↓
Rules
```

Expected:

```text
radio-platform.rules
```

---

# 21. Get Grafana Password

Retrieve password:

```powershell
[System.Text.Encoding]::UTF8.GetString(
[System.Convert]::FromBase64String(
(kubectl get secret `
-n monitoring `
monitoring-grafana `
-o jsonpath="{.data.admin-password}")
))
```

Username:

```text
admin
```

---

# 22. Access Grafana

Port-forward:

```powershell
kubectl port-forward `
-n monitoring `
svc/monitoring-grafana `
3000:80
```

Open:

```text
http://localhost:3000
```

Login:

```text
admin
<password>
```

---

# 23. Import Dashboard

Navigate:

```text
Dashboards
↓
New
↓
Import
```

Upload:

```text
observability/dashboards/radio-recording-platform.json
```

Expected:

```text
Dashboard loads successfully
```

---

# 24. Verify Health Endpoints

Port-forward:

```powershell
kubectl port-forward `
deployment/synthetic-generator `
8000:8000 `
-n radio-platform
```

Test liveness:

```powershell
curl.exe http://localhost:8000/health/live
```

Expected:

```text
OK
```

---

Test readiness:

```powershell
curl.exe http://localhost:8000/health/ready
```

Expected:

```text
READY
```

---

Test metrics:

```powershell
curl.exe http://localhost:8000/metrics
```

Expected:

```text
recordings_generated_total
```

---

# 25. Alert Validation

The following operational alert tests have been validated.

## GeneratorPodDown

Validation:

```powershell
kubectl scale deployment synthetic-generator `
--replicas=0 `
-n radio-platform
```

Expected:

```text
GeneratorPodDown
FIRING
```

Restore:

```powershell
kubectl scale deployment synthetic-generator `
--replicas=1 `
-n radio-platform
```

---

## UploadFailuresDetected

Validation:

Break IRSA role temporarily.

Verify:

```text
AssumeRoleWithWebIdentity
AccessDenied
```

in application logs.

Expected:

```text
UploadFailuresDetected
FIRING
```

---

## UploadFailureRateHigh

Expected after repeated upload failures:

```text
UploadFailureRateHigh
FIRING
```

---

## HighCpuUsage

Validation:

```powershell
kubectl exec -it `
-n radio-platform `
<pod-name> `
-- sh
```

Run:

```sh
yes > /dev/null
```

Expected:

```text
HighCpuUsage
PENDING
→
FIRING
```

Stop:

```sh
Ctrl+C
```

---

# Troubleshooting

## Deployment Rollout Stalled

Check:

```powershell
kubectl rollout status deployment/synthetic-generator `
-n radio-platform
```

If:

```text
deployment exceeded its progress deadline
```

Investigate scheduling:

```powershell
kubectl describe pod <pod-name> `
-n radio-platform |
Select-String "Events:" -Context 0,20
```

Example:

```text
FailedScheduling
Too many pods
```

---

## ServiceMonitor Not Scraping

Verify ServiceMonitor label:

```yaml
release: monitoring
```

Verify Prometheus selector:

```powershell
kubectl get prometheus `
monitoring-kube-prometheus-prometheus `
-n monitoring `
-o yaml |
Select-String "serviceMonitorSelector" -Context 0,5
```

---

## PrometheusRule Not Loaded

Verify labels:

```powershell
kubectl get prometheusrule `
radio-platform-alerts `
-n monitoring `
--show-labels
```

Expected:

```text
release=monitoring
```

Verify rule selector:

```powershell
kubectl get prometheus `
monitoring-kube-prometheus-prometheus `
-n monitoring `
-o yaml |
Select-String "ruleSelector" -Context 0,5
```

---

## Metrics API Not Available

Current platform status:

```text
kubectl top
```

returns:

```text
Metrics API not available
```

Metrics Server is not currently installed.

Prometheus remains the source of truth for resource monitoring.

---

# Platform Operational Checklist

Infrastructure:

```text
✅ Terraform Applied

✅ VPC Created

✅ EKS Running

✅ Node Ready
```

Application:

```text
✅ Image Built

✅ Image Pushed

✅ Namespace Created

✅ Service Account Created

✅ IRSA Verified

✅ Application Running

✅ Uploads Reaching S3
```

Observability:

```text
✅ Prometheus Running

✅ Grafana Running

✅ ServiceMonitor Working

✅ PrometheusRule Loaded

✅ Metrics Scraped

✅ Dashboard Imported

✅ Health Checks Working
```

Alerting:

```text
✅ GeneratorPodDown Validated

✅ UploadFailuresDetected Validated

✅ UploadFailureRateHigh Validated

✅ HighCpuUsage Validated
```

---

# Current Version

```text
v0.5.7

Features:
- Prometheus Metrics
- Grafana Dashboards
- PrometheusRule Alerting
- Alert Validation
- IRSA Authentication
- Health Endpoints
- Liveness Probe
- Readiness Probe
- Startup Probe
- Resource Requests & Limits
- Fault Injection Testing
```

---

# Next Development Milestones

1. AlertManager Integration
2. Incident Response Runbooks
3. Recording Gap Detector Service
4. Business Health Metrics
5. Durable Upload Recovery
6. Upload Retry Workflows
7. SLO Monitoring
8. Metrics Server Deployment
9. Auto-Provision Dashboard via ConfigMap
10. Observability-as-Code
