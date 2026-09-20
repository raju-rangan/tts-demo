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
| **GCS Nearline** | S3 Standard-IA | Accessed ~monthly. 30-day minimum. |
| **GCS Coldline** | S3 Glacier Instant Retrieval | Accessed ~quarterly. 90-day minimum. |
| **GCS Archive** | S3 Glacier Deep Archive | Accessed <1x/year. 365-day minimum. **Key differentiator: retrieval is still milliseconds**, unlike Glacier. If the exam says "archival but must be readable immediately," Archive is fine. |
| **GCS Autoclass** | S3 Intelligent-Tiering | Unknown/unpredictable access patterns; let Google tier it. |
| **Object Lifecycle Management** | S3 Lifecycle Rules | Age/version-based tiering and deletion. |
| **Bucket Lock / Retention Policy** | S3 Object Lock (Compliance) | WORM for SEC/FINRA/HIPAA retention. Locked = irreversible. |
| **Dual-region / Multi-region bucket** | S3 CRR / Multi-Region Access Point | Multi-region = geo-redundant reads and HA. Dual-region = turbo replication (15-min RPO SLA) between two specific regions. |
| **Persistent Disk (PD)** | EBS | VM block storage. pd-standard (HDD), pd-balanced (default), pd-ssd, pd-extreme. Can be **regional** (synchronous 2-zone replication) — no EBS equivalent. |
| **Hyperdisk** | EBS io2 Block Express / gp3 | Newest gen; independently scale IOPS/throughput/capacity on 3rd-gen+ VMs. |
| **Local SSD** | EC2 Instance Store | Ephemeral scratch, highest IOPS, data lost on stop. Caches, temp shuffle space. |
| **Filestore** | EFS | NFS for lift-and-shift apps needing a POSIX shared filesystem, GKE RWX volumes, render farms. Tiers: Basic, Zonal, Regional, Enterprise. |
| **NetApp Volumes** | FSx for ONTAP | SMB/CIFS + NFS enterprise features, Windows workloads, snapshots/clones. |
| **Parallelstore** | FSx for Lustre | HPC/AI training scratch requiring extreme parallel throughput. |
| **Storage Transfer Service** | DataSync | Online transfer from S3/Azure/on-prem/HTTP into GCS, scheduled and incremental. |
| **Transfer Appliance** | Snowball / Snowmobile | Offline bulk transfer when the link would take too long (rule of thumb: >1 month over the wire). |
| **Backup and DR Service** | AWS Backup | Centralized, policy-driven backup for GCE, VMware, databases. |

**Bandwidth math the exam loves:** hours ≈ (TB × 8000) / (Gbps × 3600). If the answer comes out in weeks or months → Transfer Appliance or Interconnect.

---

## 3. Databases

| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **Cloud SQL** | RDS (MySQL/Postgres/SQL Server) | Default relational OLTP under ~64 TB, regional. HA = synchronous standby in another zone. Read replicas can be cross-region. |
| **Cloud SQL Enterprise Plus** | RDS with higher SLA | Near-zero downtime maintenance, data cache, 99.99%. |
| **AlloyDB** | Aurora PostgreSQL | Postgres-compatible, much faster OLTP, columnar engine for analytics. Choose when "Postgres, but Aurora-class performance / HTAP." |
| **Cloud Spanner** | No true equivalent (Aurora Global + DynamoDB hybrid) | **Global, horizontally scalable, strongly consistent relational with external consistency and 99.999% multi-region SLA.** Keywords: "global transactions," "unlimited scale + SQL + ACID," financial ledgers, worldwide gaming leaderboards. |
| **Bigtable** | DynamoDB / Keyspaces (HBase API) | Petabyte-scale wide-column NoSQL, single-digit ms, very high write throughput. Time-series, IoT, AdTech, fintech ticks. **No joins, no multi-row ACID.** Row-key design is the whole exam question. |
| **Firestore (Native mode)** | DynamoDB + AppSync | Mobile/web app backend, offline sync, real-time listeners, document model. |
| **Firestore in Datastore mode** | DynamoDB | Server-side document DB without realtime/offline features. |
| **Memorystore (Redis / Valkey / Memcached)** | ElastiCache | Caching layer, session store, leaderboards. |
| **BigQuery** | Redshift / Athena | Serverless petabyte OLAP warehouse. Also the answer for "ad-hoc SQL on a data lake." |
| **Bare Metal Solution / Oracle Database@Google Cloud** | RDS for Oracle / Outposts | Oracle workloads that must stay Oracle. |
| **Datastream** | DMS (CDC) | Serverless CDC replication from Oracle/MySQL/Postgres into BigQuery/GCS. |
| **Database Migration Service** | DMS | Homogeneous and heterogeneous migration into Cloud SQL/AlloyDB with minimal downtime. |

**Selection flowchart (memorize — it's worth several questions):**

```
Structured?
├─ No  → Cloud Storage
└─ Yes → Analytics / OLAP workload?
         ├─ Yes → BigQuery
         └─ No (OLTP) → Needs SQL + joins + relational schema?
                  ├─ Yes → Global scale, >64TB, or extreme QPS?
                  │        ├─ Yes → Spanner
                  │        └─ No  → Cloud SQL (AlloyDB if perf-hungry)
                  └─ No  → Huge writes + key/range scans + low latency?
                           ├─ Yes → Bigtable
                           └─ No  → Firestore
```

---

## 4. Networking

| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **VPC** | VPC | **GCP VPCs are global**; subnets are regional. One VPC can span every region — a big mental shift from AWS. |
| **Shared VPC** | AWS RAM + Transit Gateway (partly) | Central host project owns the network; service projects attach. The standard enterprise landing-zone answer. |
| **VPC Network Peering** | VPC Peering | Private RFC1918 connectivity between VPCs; non-transitive, no overlapping CIDRs. |
| **Network Connectivity Center** | Transit Gateway | Hub-and-spoke across many VPCs / on-prem sites, transitive routing. |
| **Cloud Interconnect (Dedicated)** | Direct Connect | 10/100 Gbps private link from a colocation facility; up to 99.99% with redundant pairs. |
| **Partner Interconnect** | Direct Connect Partner | 50 Mbps–50 Gbps via a service provider when you can't reach a colo. |
| **Cloud VPN (HA VPN)** | Site-to-Site VPN | Encrypted over the internet; 99.99% SLA with HA VPN. Cheap and fast to stand up. |
| **Cross-Cloud Interconnect** | — | Direct private link to AWS/Azure. |
| **Cloud Router** | VGW / BGP | Dynamic BGP route exchange for Interconnect and VPN. |
| **Global External Application LB** | CloudFront + ALB + Global Accelerator | **Single global anycast IP**, cross-region failover, no pre-warming. Keyword: "one IP, users worldwide, HTTP(S)." |
| **Regional External Application LB** | ALB | Regional HTTP(S) when data residency or specific regional features are required. |
| **External passthrough Network LB** | NLB | TCP/UDP, preserves client IP, regional. |
| **Internal Application / Network LB** | Internal ALB / NLB | Internal tiers only. |
| **Cloud CDN** | CloudFront | Edge caching enabled as a checkbox on the global ALB, not a separate distribution. |
| **Media CDN** | CloudFront (streaming) | Large-scale video/OTT delivery on YouTube's edge. |
| **Cloud Armor** | AWS WAF + Shield | L7 WAF, OWASP rules, DDoS, geo-blocking, rate limiting, bot management. Attaches to the global ALB. |
| **Cloud NAT** | NAT Gateway | Managed egress for private instances — no instances to run or scale. |
| **Cloud DNS** | Route 53 | 100% SLA public DNS, private zones, DNS peering and forwarding to on-prem. |
| **Private Service Connect** | PrivateLink | Consume Google APIs or producer/partner services over private IPs. |
| **Private Google Access** | VPC Gateway Endpoint (S3/DDB) | Let VMs without external IPs reach Google APIs. |
| **VPC Service Controls** | No equivalent | Security perimeter around managed services (GCS/BQ) to stop data exfiltration. Very common in "regulated data" questions. |
| **Firewall rules / Network Firewall Policies** | Security Groups + NACLs | Stateful, prioritized, applied by **network tags or service accounts** at the VPC level. |
| **Cloud Service Mesh / Anthos Service Mesh** | App Mesh | mTLS, traffic splitting, observability across GKE and VMs. |

---

## 5. Data & Analytics

| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **BigQuery** | Redshift + Athena | Serverless warehouse, separated storage/compute, streaming inserts, BI Engine, federated queries. The default analytics answer. |
| **BigQuery Omni** | Redshift Spectrum (cross-cloud) | Query data sitting in S3/Azure without moving it. |
| **BigLake** | Lake Formation | Unified fine-grained governance across data lake + warehouse tables. |
| **Pub/Sub** | SNS + SQS combined | Global, serverless, at-least-once messaging; decoupling, fan-out, streaming ingestion. |
| **Pub/Sub Lite** | Kinesis Data Streams (cost-optimized) | Zonal, pre-provisioned capacity; cheaper, lower availability. Deprecating — just know it exists. |
| **Dataflow** | Kinesis Data Analytics / Glue ETL / EMR streaming | Apache Beam; unified batch + stream, autoscaling, exactly-once. Keyword: "streaming ETL with windowing / late data." |
| **Dataproc** | EMR | Existing Hadoop/Spark/Hive jobs — lift-and-shift OSS big data. Use ephemeral clusters + GCS instead of HDFS. |
| **Dataproc Serverless** | EMR Serverless | Spark without cluster sizing. |
| **Dataprep** | Glue DataBrew | Visual, no-code data wrangling for analysts. |
| **Data Fusion** | Glue Studio | GUI drag-and-drop ETL (CDAP) with 150+ connectors. |
| **Cloud Composer** | MWAA (Managed Airflow) | Orchestrate multi-service pipelines with DAGs and dependencies. |
| **Dataplex** | Glue Data Catalog + Lake Formation | Data mesh: catalog, lineage, quality, discovery across lakes. |
| **Looker / Looker Studio** | QuickSight | Enterprise BI with a semantic layer (Looker) vs. free lightweight dashboards (Looker Studio). |
| **Dataform** | dbt | SQL-based in-warehouse transformation (ELT) with version control. |

**Streaming reference architecture (draw this — it answers many questions):**

```
IoT / App → Pub/Sub → Dataflow → BigQuery → Looker
                         ├─→ Bigtable  (low-latency serving)
                         └─→ GCS       (raw archive)
```

---

## 6. AI / ML

| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **Vertex AI (platform)** | SageMaker | Unified train/tune/deploy/monitor. Custom models, pipelines, feature store, model registry, endpoints. |
| **Vertex AI AutoML** | SageMaker Autopilot / Canvas | Custom model from your labeled data, no ML expertise on the team. |
| **Vertex AI Workbench** | SageMaker Studio / Notebooks | Managed JupyterLab. |
| **Vertex AI Pipelines** | SageMaker Pipelines | Kubeflow/TFX MLOps orchestration, reproducible training. |
| **Model Garden / Gemini API** | Bedrock | Foundation models (Gemini, Claude, Llama, Gemma) — prompt, tune, serve. |
| **Vertex AI Search / Agent Builder** | Kendra + Lex + Bedrock Agents | RAG search over enterprise corpora, chatbots and agents. |
| **Vision API** | Rekognition (image) | Pretrained labels, OCR, faces, safe-search. "No training data, need it today." |
| **Video Intelligence API** | Rekognition Video | Shot detection, labels, explicit content in video. |
| **Speech-to-Text** | Transcribe | Audio → text, many languages, speaker diarization. |
| **Text-to-Speech** | Polly | Speech synthesis, WaveNet/Chirp voices. |
| **Translation API** | Translate | Translation; AutoML Translation for domain glossaries. |
| **Natural Language API** | Comprehend | Entities, sentiment, syntax, classification. |
| **Document AI** | Textract | Forms, invoices, IDs, contracts — structured extraction from documents. |
| **CCAI / Dialogflow CX** | Connect + Lex | IVR, virtual agents, agent assist. |
| **Recommendations AI** | Personalize | Retail product recommendations. |
| **TPUs / GPUs on GCE & GKE** | Trainium / Inferentia / P-instances | Large-scale training. TPU = TensorFlow/JAX heavy matrix workloads. |
| **BigQuery ML** | Redshift ML | Train models with SQL where the data already lives; for analysts, not ML engineers. |

**Decision rule:** Pretrained API → BigQuery ML → AutoML → Vertex custom training. Move right only when the simpler option can't meet accuracy or domain needs.

---

## 7. Identity, Security & Compliance

| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **Cloud IAM** | IAM | Allow-only, additive policies on the resource hierarchy. Roles: Basic → Predefined → Custom (prefer predefined). |
| **Service Accounts** | IAM Roles for EC2/Lambda | Workload identity. Attach to VM/GKE/Cloud Run; avoid downloading keys. |
| **Workload Identity Federation** | IAM Roles Anywhere / OIDC federation | Let AWS/Azure/GitHub/on-prem workloads impersonate a GCP SA — **the answer to "how do we avoid service account keys."** |
| **Cloud Identity** | IAM Identity Center | User/group directory, SSO, sync from AD via Google Cloud Directory Sync (GCDS). |
| **Resource Manager (Org → Folder → Project)** | Organizations / OUs / Accounts | **Project ≈ AWS account** as the billing, quota, and isolation unit. |
| **Organization Policy Service** | Service Control Policies (SCPs) | Constraints: disable external IPs, restrict regions, require OS Login, restrict domains. |
| **Cloud KMS / Cloud HSM / Cloud EKM** | KMS / CloudHSM / External Key Store | CMEK = customer-managed keys. CSEK = customer-supplied. **EKM = keys stay outside Google** → the "hold your own keys, regulated" answer. |
| **Secret Manager** | Secrets Manager | API keys, passwords, certs with versioning and IAM. |
| **Security Command Center (SCC)** | Security Hub + GuardDuty + Inspector | Central posture management, threat detection, vulnerability findings, compliance reports. |
| **Cloud Audit Logs** | CloudTrail | Admin Activity (always on, free), Data Access (opt-in, chatty), System Event, Policy Denied. |
| **Access Transparency / Access Approval** | No real equivalent | Log and explicitly approve Google-staff access to your data. Regulated-industry answer. |
| **Assured Workloads** | GovCloud / compliance packages | FedRAMP, CJIS, IL4, EU data-boundary control packs. |
| **Sensitive Data Protection (Cloud DLP)** | Macie | Discover, classify, mask, tokenize PII. |
| **Binary Authorization** | ECR signing + deploy policies | Only attested container images may deploy. Supply-chain questions. |
| **reCAPTCHA Enterprise** | WAF bot control | Fraud and bot defense on web flows. |
| **IAP / BeyondCorp Enterprise** | Verified Access | Zero-trust app access without a VPN. **IAP** is the go-to for "expose an internal app to remote employees securely." |
| **Certificate Manager / Google-managed certs** | ACM | TLS certificates on load balancers. |

---

## 8. Operations, DevOps & Management

| GCP Service | AWS Equivalent | When to choose |
|---|---|---|
| **Cloud Monitoring** | CloudWatch Metrics | Dashboards, uptime checks, alerting policies, SLO monitoring. |
| **Cloud Logging** | CloudWatch Logs | Log router/sinks → GCS (cheap archive), BigQuery (analysis), Pub/Sub (stream out). Log buckets with retention. |
| **Cloud Trace** | X-Ray | Distributed latency tracing. |
| **Cloud Profiler** | CodeGuru Profiler | Continuous CPU/heap profiling in production. |
| **Error Reporting** | (Sentry-like) | Aggregates and dedupes stack traces. |
| **Cloud Build** | CodeBuild + CodePipeline | Managed CI/CD; builds containers, triggers on repo events. |
| **Artifact Registry** | ECR + CodeArtifact | Containers *and* language packages (Maven/npm/Python) with vulnerability scanning. |
| **Cloud Deploy** | CodeDeploy | Progressive delivery to GKE/Cloud Run with approvals and rollbacks. |
| **Cloud Source Repositories** | CodeCommit | Hosted git (rarely the "right" answer now; most orgs use GitHub/GitLab). |
| **Infra Manager / Terraform / Config Controller** | CloudFormation / CDK | IaC. Terraform is the practical default; Infra Manager is managed Terraform. |
| **Deployment Manager** | CloudFormation | Legacy GCP-native IaC — still appears in older exam items. |
| **Cloud Scheduler** | EventBridge Scheduler | Cron for HTTP and Pub/Sub targets. |
| **Cloud Tasks** | SQS (with per-task control) | Async task queue with rate limiting, retries, per-task scheduling. |
| **Eventarc** | EventBridge | Route CloudEvents from 100+ GCP sources to Cloud Run/Functions/Workflows. |
| **Workflows** | Step Functions | Serverless orchestration of API/service calls with retries and branching. |
| **Cloud Billing + Budgets / BigQuery billing export** | Cost Explorer + Budgets + CUR | Budgets and alerts, labels for chargeback, export to BQ for analysis. |
| **Recommender / Active Assist** | Trusted Advisor / Compute Optimizer | Rightsizing, idle resources, IAM over-permission recommendations. |
| **OS Config / OS Login / Patch Management** | Systems Manager (SSM) | Patch, inventory, and SSH via IAM (OS Login) instead of key files. |
| **Migration Center** | Migration Hub + Application Discovery | Discovery, assessment, and TCO for the on-prem estate. |
| **Anthos / GKE Enterprise** | EKS Anywhere + Outposts | Consistent K8s + policy + mesh across on-prem, GCP, AWS, Azure. The hybrid/multicloud keyword. |

---

## 9. Pricing & Commitment Models (high-yield, low-effort points)

| GCP Concept | AWS Equivalent | When to choose |
|---|---|---|
| **Sustained Use Discounts (SUD)** | None — no AWS analog | Automatic discount for running a VM most of the month. Nothing to buy or manage. |
| **CUD — resource-based** | Reserved Instances | Commit to vCPU/RAM in a region for 1 or 3 years. |
| **CUD — spend-based (Flex)** | Savings Plans | Commit to a `$/hour` spend across services; more flexible. |
| **Spot / Preemptible VMs** | Spot Instances | Up to 60–91% off for interruptible work. |
| **Custom machine types** | None | Right-size vCPU:RAM exactly. Classic cost-optimization answer with no AWS equivalent. |
| **BigQuery on-demand vs. Editions (slots)** | Athena vs. Redshift RA3/Serverless | Unpredictable/ad-hoc → on-demand per-TB. Steady heavy usage → reserved slots. |
| **Free intra-region traffic / tiered network pricing** | Data transfer pricing | Co-locate chatty services in the same region/zone to cut cost — useful for eliminating distractors. |

---

## 10. GCP ≠ AWS: Traps to Internalize

> [!IMPORTANT]
> These are where AWS-experienced candidates lose points.

| Assumption from AWS | Reality in GCP |
|---|---|
| "VPCs are regional" | **VPCs are global**; subnets are regional. One VPC can host resources in every region. |
| "Accounts are the isolation boundary" | **Projects** are. Org → Folders → Projects → Resources. Billing, quota, and IAM all bind to projects. |
| "LBs need pre-warming / regional DNS failover" | The global ALB is a **single anycast IP** with instant scale and built-in cross-region failover. |
| "Archive tier means hours to restore" | GCS Archive restores in **milliseconds**; the penalty is minimum storage duration and retrieval fees, not latency. |
| "IAM has explicit Deny everywhere" | The base model is **allow-only and additive down the hierarchy**. IAM Deny policies exist but are a separate, newer construct. |
| "I need a NAT instance fleet" | **Cloud NAT** is a managed SDN feature, not instances. |
| "Firewall rules bind to instances or SGs" | Rules bind via **network tags or service accounts**, apply at the VPC level, and are stateful with priorities. |
| "Multi-region strong consistency isn't possible" | **Spanner** does exactly that (TrueTime, external consistency). It's the answer whenever global + relational + strong consistency appear together. |
| "Warehouse means cluster sizing" | **BigQuery** is serverless; you tune slots/reservations, not nodes. |
| "I must build cross-region replication for DR" | Check whether a **multi-region GCS bucket, regional PD, or regional MIG** already meets the RPO/RTO with zero custom work. |

---

## 11. 60-Second Keyword → Service Map

| If the question says... | Answer |
|---|---|
| Global, strongly consistent, relational, ACID | **Spanner** |
| Petabyte time-series/IoT, heavy writes, ms reads | **Bigtable** |
| Ad-hoc SQL on huge datasets, serverless analytics | **BigQuery** |
| Streaming ETL, windowing, late-arriving data | **Dataflow** |
| Existing Spark/Hadoop jobs | **Dataproc** |
| Decouple producers/consumers, global ingestion | **Pub/Sub** |
| Mobile app, offline sync, realtime updates | **Firestore** |
| Lift-and-shift VMware estate | **GCVE** |
| Oracle RAC / can't virtualize | **Bare Metal Solution** |
| Hybrid or multicloud consistent Kubernetes | **Anthos / GKE Enterprise** |
| Internal app for remote users, no VPN | **IAP / BeyondCorp** |
| Prevent data exfiltration from GCS/BQ | **VPC Service Controls** |
| Keys must never live inside Google | **Cloud EKM** |
| Avoid service account keys for external workloads | **Workload Identity Federation** |
| Only signed images may deploy | **Binary Authorization** |
| Restrict regions / block external IPs org-wide | **Org Policy constraints** |
| Petabytes to move, slow link | **Transfer Appliance** |
| Continuous online sync from on-prem or S3 | **Storage Transfer Service** |
| CDC from Oracle/MySQL into BigQuery | **Datastream** |
| Orchestrate multi-step data pipeline DAGs | **Cloud Composer** |
| Orchestrate service/API calls serverlessly | **Workflows** |
| Cost: interruptible batch | **Spot VMs** |
| Cost: steady 3-year workload | **CUDs** |
| Cost: odd vCPU:RAM ratio | **Custom machine types** |

---

## 12. Suggested Study Order (given your AWS background)

1. **Resource hierarchy + IAM + Org Policy** — the biggest conceptual delta from AWS.
2. **Networking** — global VPC, Shared VPC, LB types, Interconnect vs. VPN.
3. **Database selection flowchart** — highest question density on the exam.
4. **Data pipeline patterns** — Pub/Sub → Dataflow → BigQuery, plus Dataproc for legacy Hadoop.
5. **Security/compliance add-ons** — VPC-SC, EKM, Assured Workloads, Access Approval.
6. **Case studies** — read all four official ones end to end (EHR Healthcare, Helicopter Racing League, Mountkirk Games, TerramEarth); a large share of questions is anchored to them.
7. **Pricing and commitment models** — cheap points, small surface area.
