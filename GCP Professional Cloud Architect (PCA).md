# GCP Professional Cloud Architect (PCA) — Service Cheatsheet
> [!NOTE]
> Written for someone fluent in AWS. The "When to choose" column is framed the way the PCA exam frames it: pick the *managed-est* service that meets the stated requirement, and watch for keywords (global, serverless, petabyte, regulated, lift-and-shift, hybrid).
---
## 1. Compute
| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **Compute Engine (GCE)** | EC2 | Lift-and-shift, licensed/legacy software, custom kernels, GPUs, sole-tenant nodes for compliance. Default answer for "migrate VMs as-is." |
| **Managed Instance Group (MIG)** | Auto Scaling Group | Autohealing + autoscaling + rolling updates for VMs. Regional MIG = multi-zone HA. Exam keyword: "self-healing VM fleet." |
| **Preemptible VM / Spot VM** | Spot Instances | Fault-tolerant batch, CI, rendering. Preemptible = max 24h; Spot = no 24h cap. Cheapest compute. |
| **Sole-tenant nodes** | EC2 Dedicated Hosts | Physical isolation for compliance, or BYOL per-core licensing. |
| **Google Kubernetes Engine (GKE)** | EKS | Containers with portability, complex microservices, multi-cloud/hybrid (Anthos). Autopilot = no node management; Standard = you control nodes. |
| **GKE Autopilot** | EKS Fargate | "I want K8s but no node ops / pay per pod." |
| **Cloud Run** | App Runner / Fargate + ALB | Stateless HTTP containers, scale-to-zero, request-driven. Default answer for "containerize this web app, minimal ops." |
| **Cloud Run Jobs** | ECS/Fargate tasks, AWS Batch | Run-to-completion containerized tasks, no HTTP endpoint. |
| **Cloud Functions / Cloud Run functions** | Lambda | Event-driven glue: GCS object created, Pub/Sub message, Firestore trigger. Gen2 is built on Cloud Run. |
| **App Engine Standard** | Elastic Beanstalk (ish) / Lambda | Legacy exam answer for "fully managed web app, scale to zero, sandboxed runtimes." Newer material steers you to Cloud Run. |
| **App Engine Flexible** | Elastic Beanstalk | Custom runtimes, no scale-to-zero, background processes, needs VPC access. |
| **Batch** | AWS Batch | Scheduled/queued HPC and batch jobs on managed VM pools. |
| **VMware Engine (GCVE)** | VMware Cloud on AWS | Move an entire VMware estate without refactoring. Keyword: "vSphere/NSX/vSAN as-is." |
| **Bare Metal Solution** | EC2 Bare Metal / Outposts (ish) | Oracle RAC or other workloads that cannot be virtualized, colocated next to GCP regions. |
| **Migrate to Virtual Machines** | AWS Application Migration Service (MGN) | Agent-based VM lift-and-shift with test-clone cutovers. |
**Decision rule:** Functions → Cloud Run → GKE Autopilot → GKE Standard → GCE. Move right only when a requirement forces it (stateful, long-running, custom OS, sidecars/daemonsets, GPU pinning, licensing).
---
## 2. Storage (Object / File / Block)
| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **Cloud Storage (GCS)** | S3 | Any unstructured blob: images, backups, data-lake landing zone, static site. Bucket names are a single global namespace. |
| **GCS Standard** | S3 Standard | Hot data, frequent access, no minimum duration. |