# Radio Recording Platform

A cloud-native platform prototype for generating, storing, monitoring, and operating recording data on AWS.

The platform demonstrates:

- Infrastructure as Code using Terraform
- Amazon EKS and Kubernetes workloads
- IAM Roles for Service Accounts (IRSA)
- Containerized Python applications
- Amazon S3 object storage
- Prometheus metrics collection
- Grafana operational dashboards
- Kubernetes health probes
- Operational runbooks and platform recovery
- Configuration-driven workload management

The current application generates **synthetic recording metadata**, uploads it to Amazon S3, and exposes operational metrics for monitoring and alerting. It does not yet capture live radio audio. The platform architecture and roadmap describe the future evolution toward radio stream ingestion, recording-gap detection, and production-grade media processing.

> **Design Reference:** [Solution Architecture and Design](docs/design-documentation.md)

---

# Contents

- [Project Status](#project-status)
- [Architecture](#architecture)
- [Current Data Flow](#current-data-flow)
- [Operational Validation](#operational-validation)
- [Observability](#observability)
- [Operational Resilience](#operational-resilience)
- [Repository Layout](#repository-layout)
- [Run Locally](#run-locally)
- [Infrastructure Workflows](#infrastructure-workflows)
- [Storage](#storage)
- [Security and Operational Principles](#security-and-operational-principles)
- [Release Milestones](#release-milestones)
- [Roadmap](#roadmap)
- [Technology Stack](#technology-stack)
- [Design Documentation](#design-documentation)

---

# Project Status

| Area | Status |
|--------|--------|
| AWS infrastructure provisioned with Terraform | ✅ Implemented |
| Amazon EKS cluster and managed node group | ✅ Implemented |
| Containerized Python synthetic generator | ✅ Implemented |
| Kubernetes deployment and IRSA workload identity | ✅ Implemented |
| Synthetic data uploaded to Amazon S3 | ✅ Implemented |
| Configuration-driven station onboarding | ✅ Implemented |
| Terraform validation in GitHub Actions | ✅ Implemented |
| Docker build validation in GitHub Actions | ✅ Implemented |
| Prometheus application metrics | ✅ Implemented |
| Grafana operational dashboards | ✅ Implemented |
| Kubernetes liveness, readiness, and startup probes | ✅ Implemented |
| Non-root container execution | ✅ Implemented |
| Operational runbooks | ✅ Implemented |
| Disaster recovery validation | ✅ Implemented |
| Rolling deployment validation | ✅ Implemented |
| AlertManager integration | 🚧 In Progress |
| Prometheus alerting rules | 🚧 In Progress |
| Recording-gap detection service | Planned |
| Real radio stream recording | Planned |
| Multi-environment deployment support | Planned |

The platform has been successfully destroyed and recreated using Terraform and operational runbooks, validating that infrastructure and deployment processes are reproducible and recoverable.

---

# Architecture

## Implemented Prototype

```text
GitHub Actions
      │
      ├── Terraform Validation
      └── Docker Build Validation
              │
              ▼
       AWS Infrastructure
       ├── Amazon VPC
       ├── Amazon EKS
       ├── Amazon ECR
       └── Amazon S3
              │
              ▼
      Kubernetes Workloads
       ├── Synthetic Generator
       ├── Service Account
       ├── Health Endpoints
       ├── Startup Probe
       ├── Readiness Probe
       └── Liveness Probe
              │
              ▼
              IRSA
              │
              ▼
            Amazon S3
              │
              ▼
       Observability Stack
       ├── Prometheus
       ├── ServiceMonitor
       ├── Grafana
       └── AlertManager
```

The application uses IAM Roles for Service Accounts (IRSA) to access AWS services without embedding credentials inside pods.

---

## Target Architecture

```text
Radio Streams
      │
      ▼
Station Registry
      │
      ▼
Desired State Controller
      │
      ├── Recorder Worker A
      ├── Recorder Worker B
      └── Recorder Worker N
              │
              ▼
     Recording Segments
              │
              ▼
      Upload Validation
              │
              ▼
           Amazon S3
              │
              ▼
      Gap Detection Service
              │
              ▼
   Monitoring and Alerting
```

The long-term architecture separates station management, recording workloads, upload validation, business monitoring, and operational alerting.

---

# Current Data Flow

The synthetic generator creates JSON recording records, uploads them to Amazon S3, and removes local files after successful delivery.

```text
Generate Recording
        │
        ▼
Create Local File
        │
        ▼
Upload to Amazon S3
        │
        ▼
Delete Local File
        │
        ▼
Repeat
```

Example record:

```json
{
  "station_id": "station-001",
  "timestamp": "2026-11-10T13:00:00Z",
  "signal_strength": 97,
  "status": "SUCCESS"
}
```

Objects are partitioned by station and timestamp:

```text
station-001/2026/11/10/13/<timestamp>.json
```

This partitioning strategy supports future analytics, retention policies, and gap-detection workflows.

---

## Dynamic Station Configuration

The generator is configuration-driven and loads stations from:

```text
app/stations.yaml
```

Example:

```yaml
stations:
  - station-001
  - station-002
  - station-003
  - station-004
  - station-005
  - station-006
```

New stations can be onboarded by updating the station configuration and deploying a new container image.

This removes hardcoded station definitions and provides a foundation for a future station registry service.

---

# Operational Validation

The platform has been validated against the following operational scenarios:

- Terraform destroy and rebuild
- Kubernetes rolling deployments
- Pod restart recovery
- Kubernetes health probe validation
- Prometheus metric collection
- Grafana dashboard recovery
- Dynamic station onboarding
- Configuration-driven application deployment
- Disaster recovery runbook execution

This validation demonstrates that the platform can be recreated, monitored, and operated using documented procedures.

---

# Observability

The platform exposes application metrics and health endpoints that support monitoring, troubleshooting, and future alerting.

## Application Metrics

The following custom Prometheus metrics are exported:

| Metric | Description |
|----------|----------|
| recordings_generated_total | Total recordings generated |
| s3_upload_success_total | Successful S3 uploads |
| s3_upload_failure_total | Failed S3 uploads |
| upload_duration_seconds | Upload latency histogram |
| generation_cycle_duration_seconds | Generation cycle latency histogram |

Metrics are exposed through:

```text
/metrics
```

and scraped automatically using a Kubernetes ServiceMonitor.

---

## Health Endpoints

The application exposes:

```text
/health/live
/health/ready
```

These endpoints support Kubernetes health management and automated remediation.

---

## Kubernetes Health Management

The deployment includes:

- Startup probes
- Liveness probes
- Readiness probes

These provide:

- Automatic unhealthy pod detection
- Automatic pod restart
- Deployment health validation
- Controlled rolling updates
- Safer application deployments

---

## Grafana Dashboard

The platform includes a custom operational dashboard designed using SRE-focused principles.

### KPI Dashboards

Business KPIs:

- Total recordings generated (24h)
- Successful uploads (24h)
- Failed uploads (1h)
- Upload failure rate (1h)
- Recording generation rate

Platform Performance:

- Average upload duration
- Upload duration per station
- Generation cycle duration

Platform Health:

- Generator pod availability
- Pod restart monitoring
- Container memory utilisation
- Container CPU utilisation

The dashboard uses `increase()` and `rate()` functions to ensure metrics remain accurate across pod restarts and rolling deployments.

Examples include:

- Upload failure rate
- Recording generation rates
- Upload latency trends
- Generation cycle latency

This approach reflects operational reality and production-style observability practices.

---

### Dashboard Screenshots

#### KPIs

![KPIs](docs/Grafana%20Dashboard%20Snapshots/KPIs.png)

#### Business Metrics

![Business Metrics](docs/Grafana%20Dashboard%20Snapshots/Buisness%20Metrics.png)

#### Platform Performance

![Platform Performance](docs/Grafana%20Dashboard%20Snapshots/Platform%20Performance.png)

#### Platform Health

![Platform Health](docs/Grafana%20Dashboard%20Snapshots/Platform%20Health.png)

---

# Operational Resilience

The platform has been validated through complete infrastructure rebuild testing.

Recovery workflow:

```text
terraform destroy
       │
       ▼
terraform apply
       │
       ▼
Provision EKS
       │
       ▼
Deploy Application
       │
       ▼
Deploy Monitoring Stack
       │
       ▼
Restore Dashboard
       │
       ▼
Verify Metrics
```

This process is documented in:

```text
docs/runbooks/platform-startup-runbook.md
```

The successful rebuild demonstrates the platform can be recreated without manual AWS configuration.

---

# Repository Layout

```text
.
├── .github/
│   └── workflows/
│
├── app/
│   ├── generator.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── stations.yaml
│
├── kubernetes/
│   ├── namespace.yaml
│   ├── serviceaccount.yaml
│   ├── deployment.yaml
│   └── service.yaml
│
├── observability/
│   ├── dashboards/
│   │   └── radio-platform-dashboard.json
│   ├── servicemonitor.yaml
│   └── prometheus-rules.yaml
│
├── terraform/
│
├── docs/
│   ├── design-documentation.md
│   ├── runbooks/
│   │   └── platform-startup-runbook.md
│   └── images/
│
└── README.md
```

---

# Run Locally

## Prerequisites

- Python
- pip
- Docker
- AWS CLI
- Terraform
- kubectl

Install dependencies:

```bash
python -m pip install -r app/requirements.txt
```

Run:

```bash
python app/generator.py
```

PowerShell:

```powershell
python -m pip install -r app\requirements.txt
python app\generator.py
```

---

## Build Container

```bash
docker build -t synthetic-generator ./app
```

Push to ECR:

```bash
docker push <ecr-repository-uri>
```

---

# Infrastructure Workflows

Terraform workflow:

```bash
cd terraform

terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

Destroy development environment:

```bash
terraform destroy
```

> **Caution:** Terraform changes real AWS resources and may incur costs.

Always verify:

- AWS account
- AWSrational Principles

## Implemented Controls

- IAM Roles for Service Accounts (IRSA)
- Non-root container execution
- Resource requests and limits
- Kubernetes health probes
- Infrastructure as Code
- GitHub Actions validation
- Private S3 storage
- Disaster recovery runbooks
- Dynamic configuration management

## Planned Controls

- AlertManager notifications
- Security scanning
- SLO monitoring
- Multi-environment promotion
- Automated recovery workflows

---

# Release Milestones

| Release | Capability |
|----------|----------|
| v0.5.4 | Health probes, non-root containers, Grafana dashboard |
| v0.5.5 | Dynamic station onboarding using stations.yaml |
| v0.5.6 | Deployment-safe observability and operational KPIs |

---

# Roadmap

## Phase 1 - Platform Foundation ✅

- Terraform infrastructure
- Amazon EKS
- Amazon ECR
- Amazon S3
- IRSA integration

## Phase 2 - Observability ✅

- Prometheus metrics
- Grafana dashboards
- ServiceMonitor integration
- Health endpoints
- Startup probes
- Liveness probes
- Readiness probes
- Disaster recovery runbooks
- Operational KPI dashboards

## Phase 3 - Alerting 🚧

- PrometheusRule definitions
- AlertManager integration
- Alert validation
- Incident response workflows

## Phase 4 - Recording Gap Detection

- Missing recording detection
- Recording freshness validation
- Coverage dashboards
- Business health metrics

## Phase 5 - Real Recording Workloads

- Live radio stream ingestion
- Recording segment management
- Upload retries
- Delivery validation

## Phase 6 - Production Hardening

- SLO reporting
- Multi-environment deployments
- Security scanning
- Automated dashboard provisioning
- Chaos testing
- Disaster recovery testing

---

# Technology Stack

| Area | Technology |
|--------|------------|
| Cloud | AWS |
| Infrastructure as Code | Terraform |
| Container Orchestration | Kubernetes |
| Managed Kubernetes | Amazon EKS |
| Container Registry | Amazon ECR |
| Object Storage | Amazon S3 |
| Workload Identity | IRSA |
| Application Runtime | Python |
| Containerization | Docker |
| Monitoring | Prometheus |
| Visualisation | Grafana |
| Alerting | AlertManager |
| CI/CD | GitHub Actions |

---

# Design Documentation

For detailed architecture, requirements, observability strategy, reliability design, and future platform evolution:

**docs/design-documentation.md**