# Radio Recording Platform

A cloud-native platform prototype for generating, storing, and operating recording data on AWS.

The platform demonstrates:

- Infrastructure as Code using Terraform
- Amazon EKS and Kubernetes workloads
- IAM Roles for Service Accounts (IRSA)
- Containerized Python applications
- Amazon S3 object storage
- Prometheus metrics collection
- Grafana dashboards
- Kubernetes health probes
- Operational runbooks and platform recovery

The current application generates **synthetic recording metadata** and uploads it to Amazon S3. It does not yet capture live radio audio. The architecture and roadmap describe how the platform will evolve toward real radio stream recording and recording-gap detection.

> **Design reference:** [Solution Architecture and Design](docs/design-documentation.md)

---

# Contents

- [Project status](#project-status)
- [Architecture](#architecture)
- [Current data flow](#current-data-flow)
- [Observability](#observability)
- [Operational resilience](#operational-resilience)
- [Repository layout](#repository-layout)
- [Run locally](#run-locally)
- [Infrastructure workflows](#infrastructure-workflows)
- [Storage](#storage)
- [Security and operational principles](#security-and-operational-principles)
- [Release milestones](#release-milestones)
- [Roadmap](#roadmap)
- [Technology stack](#technology-stack)
- [Design documentation](#design-documentation)

---

# Project status

| Area                                                | Status         |
| --------------------------------------------------- | -------------- |
| AWS infrastructure provisioned with Terraform       | ✅ Implemented |
| Amazon EKS cluster and managed node group           | ✅ Implemented |
| Containerized Python synthetic generator            | ✅ Implemented |
| Kubernetes deployment and IRSA workload identity    | ✅ Implemented |
| Synthetic data uploaded to Amazon S3                | ✅ Implemented |
| Terraform validation in GitHub Actions              | ✅ Implemented |
| Docker build validation in GitHub Actions           | ✅ Implemented |
| Prometheus application metrics                      | ✅ Implemented |
| Grafana operational dashboards                      | ✅ Implemented |
| Kubernetes liveness, readiness, and startup probes  | ✅ Implemented |
| Non-root container execution                        | ✅ Implemented |
| Platform rebuild runbook                            | ✅ Implemented |
| Disaster recovery validation                        | ✅ Implemented |
| AlertManager integration                            | 🚧 In Progress |
| Prometheus alerting rules                           | 🚧 In Progress |
| Recording-gap detection service                     | Planned        |
| Real radio stream recording                         | Planned        |
| Deployment automation and multi-environment support | Planned        |

The platform has been successfully destroyed and recreated using Terraform and operational runbooks, validating that the infrastructure and deployment process are reproducible and recoverable.

---

# Architecture

## Implemented prototype

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
        Kubernetes Workload
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

The application uses IAM Roles for Service Accounts (IRSA) to access AWS services without embedding credentials inside containers.

---

## Target architecture

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

The long-term design separates station management, recording, upload management, and business-health monitoring to support scale and operational resilience.

---

# Current data flow

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

# Observability

The platform exposes operational metrics and health endpoints that enable monitoring, troubleshooting, and future alerting.

## Application Metrics

The following custom Prometheus metrics are exported:

| Metric                            | Description                        |
| --------------------------------- | ---------------------------------- |
| recordings_generated_total        | Total recordings generated         |
| s3_upload_success_total           | Successful S3 uploads              |
| s3_upload_failure_total           | Failed S3 uploads                  |
| upload_duration_seconds           | Upload latency histogram           |
| generation_cycle_duration_seconds | Generation cycle latency histogram |

Metrics are exposed through:

```text
/metrics
```

and scraped automatically by Prometheus using a Kubernetes ServiceMonitor.

---

## Health Endpoints

The application exposes:

```text
/health/live
/health/ready
```

These endpoints support Kubernetes health management.

---

## Kubernetes Health Management

The deployment includes:

- Startup Probes
- Liveness Probes
- Readiness Probes

These provide:

- Automatic unhealthy pod detection
- Automatic pod restart
- Deployment health validation
- Controlled rolling updates

---

## Grafana Dashboard

The platform includes a custom operational dashboard built on Grafana.

### Dashboard Features

- Recording generation tracking
- Station activity monitoring
- Upload success metrics
- Upload failure visibility
- Generation latency monitoring
- Upload latency monitoring
- Resource utilization monitoring
- Pod health indicators

![KPIs](docs/Grafana%20Dashboard%20Snapshots/KPIs.png)

![Business Metrics](docs/Grafana%20Dashboard%20Snapshots/Buisness%20Metrics.png)

![Platform Health](docs/Grafana%20Dashboard%20Snapshots/Platform%20Health.png)

![Platform Performance](docs/Grafana%20Dashboard%20Snapshots/Platform%20Performance.png)


---

# Operational resilience

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

The successful rebuild demonstrates that the platform can be recreated without manual AWS configuration.

---

# Repository layout

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

# Run locally

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

## Build container

```bash
docker build -t synthetic-generator ./app
```

Push to ECR:

```bash
docker push <ecr-repository-uri>
```

---

# Infrastructure workflows

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

- AWS Account
- Region
- S3 retention expectations
- Terraform plan output

before applying changes.

---

# Storage

Current partition layout:

```text
station-id/year/month/day/hour/file.json
```

Example:

```text
station-001/2026/11/10/13/file.json
```

Future production enhancements:

- Lifecycle rules
- Encryption policies
- Duplicate handling
- Upload retries
- Recovery workflows
- Segment validation

---

# Security and operational principles

## Implemented Controls

- IAM Roles for Service Accounts (IRSA)
- Non-root containers
- Resource requests and limits
- Kubernetes health probes
- Infrastructure as Code
- GitHub Actions validation
- Private S3 storage
- Rebuild runbooks

## Planned Controls

- AlertManager notifications
- Security scanning
- SLO monitoring
- Multi-environment promotion
- Automated recovery workflows

---

# Release milestones

| Release | Capability                                                        |
| ------- | ----------------------------------------------------------------- |
| v0.5.4  | Health checks, probes, non-root containers, operational dashboard |

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
- Recovery runbooks

## Phase 3 - Alerting 🚧

- PrometheusRule definitions
- AlertManager integration
- Alert validation
- Incident response workflows

## Phase 4 - Recording Gap Detection

- Missing recording detection
- Recording freshness checks
- Coverage dashboards
- Business health metrics

## Phase 5 - Real Recording Workloads

- Radio stream ingestion
- Bounded recording segments
- Upload retries
- Delivery validation

## Phase 6 - Production Hardening

- SLO reporting
- Multi-environment deployments
- Security scanning
- Automated dashboard provisioning
- Chaos and disaster recovery testing

---

# Technology stack

| Area                    | Technology     |
| ----------------------- | -------------- |
| Cloud                   | AWS            |
| Infrastructure as Code  | Terraform      |
| Container Orchestration | Kubernetes     |
| Managed Kubernetes      | Amazon EKS     |
| Container Registry      | Amazon ECR     |
| Object Storage          | Amazon S3      |
| Workload Identity       | IRSA           |
| Application Runtime     | Python         |
| Containerization        | Docker         |
| Monitoring              | Prometheus     |
| Visualization           | Grafana        |
| Alerting                | AlertManager   |
| CI/CD                   | GitHub Actions |

---

# Design documentation

For detailed architecture, requirements, reliability strategy, observability design, and future platform evolution:

**[Solution Architecture and Design](docs/design-documentation.md)**

---

### TODO - ADD SCREENSHOTS

Recommended images:

```text
docs/images/
├── architecture
```
