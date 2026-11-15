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
docker build -t synthetic-generator:v0.5.0 .
```

Tag:

```powershell
docker tag synthetic-generator:v0.5.0 `
548722508417.dkr.ecr.eu-west-2.amazonaws.com/synthetic-generator:v0.5.0
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
548722508417.dkr.ecr.eu-west-2.amazonaws.com/synthetic-generator:v0.5.0
```

Expected:

```text
digest: sha256:...
```

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

---

# 10. Deploy Application

Verify deployment image:

```yaml
image: 548722508417.dkr.ecr.eu-west-2.amazonaws.com/synthetic-generator:v0.5.0
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

# 13. Verify S3 Uploads

Check logs for:

```text
Upload successful
```

or verify directly:

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

# 14. Create Monitoring Namespace

```powershell
kubectl create namespace monitoring
```

If namespace already exists:

```text
Monitoring namespace already exists
```

Continue.

---

# 15. Install kube-prometheus-stack

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

# 16. Wait For Monitoring Components

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

# 17. Deploy ServiceMonitor

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

# 18. Verify Prometheus

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

---

# 19. Get Grafana Password

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

# 20. Access Grafana

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

# 21. Import Dashboard

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

# 22. Verify Health Endpoints

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

✅ Application Running

✅ Uploads Reaching S3
```

Observability:

```text
✅ Prometheus Running

✅ Grafana Running

✅ ServiceMonitor Working

✅ Metrics Scraped

✅ Dashboard Imported

✅ Health Checks Working
```

---

# Current Version

```text
v0.5.0

Features:
- Prometheus Metrics
- Grafana Dashboards
- IRSA Authentication
- Health Endpoints
- Liveness Probe
- Readiness Probe
- Resource Requests & Limits
```

---

# Next Development Milestones

1. AlertManager Rules
2. Grafana Alerting
3. Recording Gap Detector Service
4. Business Health Metrics
5. SLO Monitoring
6. Auto-Provision Dashboard via ConfigMap
7. Observability-as-Code