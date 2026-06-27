# Mini Allegro — E-commerce Platform (PAW 2026 Lab Project)

> Academic project developed at the Nicolaus Copernicus University in Toruń as part of the **Large-Scale Applications (PAW)** course, academic year 2025/2026.

The project simulates an e-commerce platform inspired by Allegro, built as a **set of independent microservices** deployed on **Google Cloud Platform**. Each microservice is written in a different technology, has its own Dockerfile, its own Terraform infrastructure, and an independent CI/CD pipeline.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Microservices](#microservices)
  - [symphony-monolith (PHP / Symfony)](#symphony-monolith--php--symfony)
  - [products-service (Scala)](#products-service--scala)
  - [purchase-service (Python / Flask)](#purchase-service--python--flask)
  - [product-review-service (Java / Spring Boot)](#product-review-service--java--spring-boot)
  - [offers-service (Go)](#offers-service--go)
  - [embedding-service (Python)](#embedding-service--python)
  - [twitch-agent (Python / AI Agent)](#twitch-agent--python--ai-agent)
- [Infrastructure (GCP + Terraform)](#infrastructure-gcp--terraform)
- [Audit Log — Central Logging System](#audit-log--central-logging-system)
- [Pub/Sub — Inter-service Communication](#pubsub--inter-service-communication)
- [CI/CD (GitHub Actions)](#cicd-github-actions)
- [Integration Tests](#integration-tests)
- [Running Locally](#running-locally)
- [Team & Contributions](#team--contributions)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                        │
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────┐                       │
│  │ symphony-monolith│    │  offers-service  │                       │
│  │   PHP / Symfony  │    │       Go         │                       │
│  │   Cloud Run      │    │   Cloud Run      │──► Pub/Sub topic      │
│  └──────────┬───────┘    └──────────────────┘                       │
│             │                                                        │
│      ┌──────┴──────┐   ┌──────────────────┐                        │
│      │  delegates  │   │ purchase-service  │                        │
│      │  HTTP calls │   │  Python / Flask   │                        │
│      └──────┬──────┘   │   Cloud Run       │                        │
│             │           └──────────────────┘                        │
│  ┌──────────▼───────┐   ┌──────────────────┐                       │
│  │product-review-svc│   │ products-service  │                       │
│  │ Java/Spring Boot │   │      Scala        │                       │
│  │   Cloud Run      │   │   Cloud Run       │                       │
│  │   Firestore DB   │   └──────────────────┘                        │
│  └──────────────────┘                                               │
│                                                                     │
│  ┌──────────────────────────────────────────┐                       │
│  │           embedding-service              │                       │
│  │  Python + Qdrant (vector DB)             │                       │
│  │  Models: nomic-embed-text, gemini-emb-2  │                       │
│  └──────────────────────────────────────────┘                       │
│                                                                     │
│  ┌──────────────────────────────────────────┐                       │
│  │           Cloud SQL (PostgreSQL)         │                       │
│  │  Main data + Audit Log (partitioned)     │                       │
│  └──────────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

**GCP Project:** `paw-2026-496213`
**Region:** `europe-central2` (Warsaw)

---

## Microservices

### symphony-monolith — PHP / Symfony

**Location:** `services/symphony-monolith/`

The main application of the project. A PHP 8.3 monolith built on the **Symfony 7** framework, exposing a REST API for front-end clients. Manages the following entities: `users`, `offers`, `products`, `purchases`, `product-reviews`.

**Technologies:**
- PHP 8.3 + Symfony 7
- Doctrine ORM + database migrations
- Symfony HTTP Client (delegating requests to microservices)
- Monolog (logging)
- Symfony Serializer + Validator

**Key endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/offers` | List of offers |
| `GET` | `/users` | List of users |
| `GET` | `/products` | List of products |
| `GET` | `/purchases` | List of purchases |
| `GET` | `/purchases/offer/{id}` | Purchases for a given offer |
| `GET` | `/product-reviews` | Delegated to product-review-service |
| `POST` | `/product-reviews` | Delegated to product-review-service |
| `GET` | `/health` | Health check |
| `GET` | `/health/error` | Test endpoint — generates an error (alert testing) |

**Infrastructure:**
- Cloud Run (serverless containers)
- Cloud SQL PostgreSQL
- Artifact Registry (Docker images)
- Cloud Build (building images on the GCP side)

---

### products-service — Scala

**Location:** `services/products-service/`

Microservice managing the product catalogue. Written in **Scala** using the `sbt` build tool.

**Technologies:**
- Scala
- sbt (build tool)
- Docker
- Cloud Run

---

### purchase-service — Python / Flask

**Location:** `services/purchase-service/`

Microservice handling purchases. Written in **Python/Flask**, with its own Dockerfile and run scripts.

**Technologies:**
- Python 3 + Flask
- PostgreSQL (Cloud SQL)
- Docker
- Cloud Run

---

### product-review-service — Java / Spring Boot

**Location:** `services/product-review-service/`

Microservice handling product and offer reviews. Built as a standalone service in **Java/Spring Boot**, with its database migrated from PostgreSQL to **Google Cloud Firestore**.

**Technologies:**
- Java + Spring Boot
- Maven (`pom.xml`)
- Google Cloud Firestore (NoSQL — document database)
- Docker
- Cloud Run

**Key endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/product-reviews` | Get reviews |
| `POST` | `/product-reviews` | Add a review |
| `GET` | `/reviews-super` | Extended review view with offer_id |

The Symfony monolith delegates all `/product-reviews` requests directly to this service via HTTP Client.

---

### offers-service — Go

**Location:** `services/offers-service/`

Microservice managing offers. Written in **Go**, with database migrations and integration with **Google Cloud Pub/Sub** for event logging.

**Technologies:**
- Go (Golang)
- PostgreSQL
- Google Cloud Pub/Sub (`cloud.google.com/go/pubsub/v2`)
- Docker
- Cloud Run

**Pub/Sub architecture in this service:**
- After each `CreateOffer` and `AssignSuperSeller`, a log is published to the Pub/Sub topic `mini-allegro-service-logs`
- `NoopPublisher` fallback when `PUBSUB_TOPIC` is not set (safe local execution)

---

### embedding-service — Python

**Location:** `services/embedding-service/`

A service for **semantic document search** over a knowledge base, based on a user-provided phrase. It generates and stores vector representations (embeddings) of scientific articles from the **AI arXiv** dataset (41,584 text chunks).

**Technologies:**
- Python 3
- **Qdrant** — vector database (ANN search using HNSW algorithm)
- **Ollama** — local embeddings via `nomic-embed-text` model (768 dims)
- **Google Gemini API** — embeddings via `gemini-embedding-2` model (3072 dims)
- `qdrant-client`, `google-genai`, `datasets`, `tqdm`
- Docker Compose (local Qdrant setup)

**Dataset:**
- Source: `ai-arxiv-chunked` (arXiv papers on AI topics)
- 41,584 text chunks loaded from disk (`data/ai-arxiv-chunked/`)

**Qdrant collection schema (`ai-arxiv`):**

```json
{
  "id": 1,
  "vector": {
    "nomic-embed-text": [... 768 floats ...],
    "gemini-embedding-2": [... 3072 floats ...]
  },
  "payload": {
    "raw": "original text of the chunk"
  }
}
```

The collection uses **named vectors** — a single point stores embeddings from multiple models in separate vector spaces.

**Semantic search flow:**

```
1. User enters a phrase + selects a model (nomic or gemini)
2. System generates an embedding of the phrase using THE SAME model
3. Qdrant: filter { named_vector = "<selected model>" } + ANN search (HNSW)
4. Returns top-K most similar documents (cosine similarity)
```

**HNSW search (Hierarchical Navigable Small World):**
- Instead of comparing against every vector (O(n)), Qdrant builds a multi-layer connection graph
- Search checks ~200–500 vectors instead of millions — accuracy 95–99%
- Similarity measure: **cosine similarity** (from -1 to 1)

**Scripts:**
- `embed_and_store.py` — main script for embedding and writing to Qdrant. Supports `--limit N` for testing on a subset
- `download_dataset.py` — downloads the AI arXiv dataset
- `docker-compose.yml` — local Qdrant setup with a persistent `qdrant_data` volume

**Architectural decisions:** see `services/embedding-service/VECTOR_DB_DECISIONS.md`

---

### twitch-agent — Python / AI Agent

**Location:** `services/twitch-agent/`

An AI agent based on a large language model, integrated with the Twitch platform. Implemented in `agent.py`.

---

## Infrastructure (GCP + Terraform)

**Location:** `infra/`

All infrastructure is managed by **Terraform**. Two separate environments exist: `dev` and `prod`.

```
infra/
├── main.tf              # main GCP resources (Artifact Registry, Cloud SQL)
├── variables.tf
├── outputs.tf
├── purchase-service.tf  # resources for purchase-service
├── dev/                 # development environment
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── prod/                # production environment
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── offers-service/      # resources for offers-service
├── products-service/    # resources for products-service
├── product-review-service/ # resources for product-review-service
└── embedding-service/   # resources for embedding-service
```

**GCP resources managed by Terraform:**

| Resource | Description |
|----------|-------------|
| `google_cloud_run_service` | Hosting each microservice (serverless) |
| `google_sql_database_instance` | Cloud SQL PostgreSQL (dev + prod) |
| `google_artifact_registry_repository` | Docker image registry (`mini-allegro`) |
| `google_pubsub_topic` | Pub/Sub topic `mini-allegro-service-logs` |
| `google_pubsub_subscription` | Pull subscription (7-day retention) |
| `google_compute_instance` | VM with Elasticsearch (Audit Log) |
| `google_firestore_database` | Firestore for product-review-service |
| `google_monitoring_alert_policy` | Alert on 5+ errors in 5 minutes |

**Deployment order:**

```
terraform apply (Artifact Registry)
→ docker push (image to Artifact Registry)
→ terraform apply (Cloud Run + remaining resources)
```

**Setting up infrastructure:**

```bash
gcloud auth login
gcloud config set project paw-2026-496213
gcloud auth configure-docker europe-central2-docker.pkg.dev

cd infra
terraform init
terraform apply -var="alert_email=your.email@domain.com"
```

---

## Audit Log — Central Logging System

**Documentation:** `audit-log-design.md`

A central system storing the history of all entity operations across the entire project. Based on **event sourcing** — every CREATE/UPDATE/DELETE operation is recorded as an immutable log entry.

**Database:** PostgreSQL (Cloud SQL) with an `audit_logs` table partitioned quarterly by the `timestamp` column.

**Log structure:**

```json
{
  "timestamp": "2026-05-06T10:23:00Z",
  "entity": "product",
  "operation": "CREATE",
  "payload": { "id": 42, "name": "Laptop", "price": 3499.99 },
  "endpoint": "/products/42"
}
```

**Supported entities:** `product`, `purchase`, `review`, `user`
**Supported operations:** `CREATE`, `UPDATE` (delta — changed fields only), `DELETE` (payload = NULL)

**Indexing:**

| Index type | Column | Rationale |
|------------|--------|-----------|
| BRIN | `timestamp` | Append-only data inserted chronologically — a fraction of B-tree size |
| B-tree | `entity`, `operation` | Fast filtering over a fixed set of values |
| GIN | `payload` (JSONB) | Indexes every key and value inside JSON — without it, every query is a full table scan |

**Partitioning:**
```sql
CREATE TABLE audit_logs (...)
PARTITION BY RANGE (timestamp);

-- Q2 2026
CREATE TABLE audit_logs_2026_q2 PARTITION OF audit_logs
FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
```

**`audit-log-service` API:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/logs` | Write a log entry |
| `GET` | `/logs` | Retrieve all logs |
| `GET` | `/logs?entity=product` | Filter by entity |
| `GET` | `/logs?operation=DELETE` | Filter by operation |

---

## Pub/Sub — Inter-service Communication

**Topic:** `mini-allegro-service-logs`
**Schema:** Protobuf with fields `timestamp`, `entity`, `operation`, `payload`, `endpoint`

Currently integrated with `offers-service` — event logs for `CreateOffer` and `AssignSuperSeller` are published to the topic. The architecture anticipates connecting the remaining services.

---

## CI/CD (GitHub Actions)

**Location:** `.github/workflows/`

Each microservice has its own pipeline. Main workflow `deploy.yml`:

1. **Build** — `gcloud builds submit` or `docker buildx` with cache in Artifact Registry
2. **Deploy DEV** — `terraform apply` → Cloud Run DEV
3. **Health check** — verifies the `/health` endpoint
4. **Integration tests** — `pytest` (separately for `offers`, `users`, `products`)
5. **Auto-PR** — automatically creates a PR `develop → main` after a successful DEV health check
6. **Deploy PROD** — after merge to `main`

**Production deployment with automatic rollback:**

```bash
./services/symphony-monolith/scripts/deploy_prod_with_rollback.sh \
  --service mini-allegro \
  --region europe-central2 \
  --project paw-2026-496213 \
  --image europe-central2-docker.pkg.dev/paw-2026-496213/mini-allegro/mini-allegro:latest
```

The script saves the previous Cloud Run revision and rolls back via `gcloud run services update-traffic` if the health check fails.

**Required GitHub Actions secrets:**

| Secret | Description |
|--------|-------------|
| `DEV_DATABASE_URL` | Cloud SQL DEV connection string |
| `PROD_DATABASE_URL` | Cloud SQL PROD connection string |
| `TF_STATE_BUCKET` | GCS bucket name for Terraform state |

---

## Integration Tests

Tests are written in **pytest** (Python) and fire HTTP requests against a running application instance.

```
integ-tests/
├── test_offers.py
├── test_users.py
└── test_products.py
```

**Running locally:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/symphony-monolith/requirements-dev.txt

pytest integ-tests/test_offers.py
pytest integ-tests/test_users.py
pytest integ-tests/test_products.py
```

By default, tests target `http://localhost:8080`. The URL can be overridden:

```bash
APP_BASE_URL=https://your-service.run.app pytest integ-tests/
```

---

## Running Locally

**Helper script:**

```bash
./scripts/local-app.sh up      # start the application (Docker Compose)
./scripts/local-app.sh test    # run integration tests
./scripts/local-app.sh logs    # view logs
./scripts/local-app.sh status  # check status
./scripts/local-app.sh stop    # stop
./scripts/local-app.sh down    # remove containers
```

`local-app.sh` automatically fetches `DATABASE_URL` from Terraform (`infra/dev`) — the local instance connects to the DEV database on Cloud SQL.

**Running embedding-service locally:**

```bash
cd services/embedding-service

# Start Qdrant (vector DB)
docker compose up -d

# Download the dataset
python download_dataset.py

# Run embedding (e.g. first 500 records for testing)
python embed_and_store.py --limit 500

# Qdrant dashboard available at: http://localhost:6333/dashboard
```

`GEMINI_API_KEY` environment variable is required for Gemini embeddings.
For Ollama embeddings: `ollama serve` + `ollama pull nomic-embed-text`.

---

## Team & Contributions

This project was developed by **4 people** over the course of the 2025/2026 semester.

### Łukasz Błok — personal contribution

#### 1. CI/CD and base infrastructure — from scratch

Set up the complete GitHub Actions pipeline for the project as one of the first contributors:
- `deploy.yml` workflow — Docker image build, deploy to Cloud Run, health check, integration tests
- Automatic PR creation `develop → main` after a successful DEV health check
- Added deployment links to GitHub Actions summary (commit URL, PR URL, service URL)
- First skeleton Terraform infrastructure (`hello-lukasz`)
- Fixed a series of pipeline issues: `pull-requests write` permissions, checkout before `gh pr create`, IAM binding for public access, Symfony autoloader inside the container

#### 2. Product Review Service — Java / Spring Boot

The largest functional contribution in the project:

- **Service skeleton** `product-review-service` in Java/Spring Boot from scratch (hardcoded data → PostgreSQL → Firestore)
- **Database migration** from PostgreSQL to **Google Cloud Firestore** (storage architecture change)
- **Terraform infrastructure** for the service (Cloud Run, Firestore) in a separate module
- **Integration with the Symfony monolith** — delegating `GET /product-reviews` and `POST /product-reviews` from the monolith to the microservice via Symfony HTTP Client
- Added `symfony/http-client` to the monolith dependencies
- Increased HTTP Client timeout (handling Cloud Run cold start)
- Added `offer_id` as a foreign key and `/reviews-super` endpoints
- Integration tests for reviews (`integ-tests/`)
- CI/CD for feature branches of the service (separate `feature.yml` workflow)
- Fixed duplicate Firestore resource blocks in Terraform

#### 3. Audit Log Service

- Designed and implemented a central operation logging service (event sourcing)
- `audit_logs` architecture in PostgreSQL: table partitioned quarterly by `timestamp`
- Indexing: BRIN on timestamp, B-tree on entity/operation, GIN on JSONB payload
- Terraform infrastructure: VM with **Elasticsearch** on GCP Compute Engine
- Automatic VM restart on connection error (`auto-start Elasticsearch VM on connection error`)
- Fixed Compute Engine API setup (`google_project_service` before creating VM and firewall rules)
- Added `AUDIT_LOG_SERVICE_URL` to the environment of all services

#### 4. Embedding Service — semantic document search

Built the embedding pipeline for a semantic search system over the AI arXiv knowledge base:

- `embed_and_store.py` script — loads 41,584 text chunks from the AI arXiv dataset and stores their embeddings in Qdrant
- Integration with **two embedding models simultaneously**:
  - `nomic-embed-text` (768 dims) via **Ollama** (locally)
  - `gemini-embedding-2` (3072 dims) via **Google Gemini API**
- **Named vectors** architecture in Qdrant — one collection, two separate vector spaces; the user selects the model in the UI
- Batch processing (50 records per batch), `tqdm` progress bar, `--limit` parameter for testing
- Debugging and migration from the deprecated `google.generativeai` to the new `google.genai` SDK
- Persistent Qdrant storage configuration (Docker volume `qdrant_data`)
- Architectural decision documentation: `VECTOR_DB_DECISIONS.md` (Qdrant vs pgvector/Pinecone/Weaviate, HNSW algorithm description, cosine similarity)

**Semantic search flow implemented by Łukasz:**
```
user enters a phrase + selects a model
→ system generates embedding of the phrase using that same model
→ Qdrant ANN search (HNSW) in the selected named vector space
→ top-K most similar chunks from scientific articles are returned
```

#### 5. Integrations and merges

- Added the `symfony-purchase` microservice (a colleague's work) to the main repo without disrupting existing changes
- Repeatedly resolved merge conflicts in the `product-review-service` Terraform (`main.tf`)
- Merged `fixed → develop` branches

---

## Technologies Used by Łukasz Błok

### Programming languages and frameworks

| Technology | Usage |
|------------|-------|
| **Java** | Implementation of `product-review-service` (Spring Boot) |
| **Spring Boot** | Framework for the review microservice — REST API, dependency injection, configuration |
| **Python 3** | Embedding service scripts (`embed_and_store.py`, `download_dataset.py`) and integration tests (pytest) |
| **PHP 8.3 / Symfony 7** | Extending the monolith — HTTP Client integration with the review microservice |

### Databases and storage

| Technology | Usage |
|------------|-------|
| **PostgreSQL** | Main application database and `audit_logs` table (Cloud SQL) |
| **Google Cloud Firestore** | Storage migration for `product-review-service` from PostgreSQL to NoSQL |
| **Qdrant** | Vector database for storing embeddings (named vectors, HNSW ANN search) |
| **Elasticsearch** | VM on GCP Compute Engine — backend for the Audit Log Service |

### AI / ML / Embeddings

| Technology | Usage |
|------------|-------|
| **Google Gemini API** (`google-genai`) | Generating embeddings via `gemini-embedding-2` model (3072 dims) |
| **Ollama** | Local embedding generation via `nomic-embed-text` model (768 dims) |
| **Qdrant** (HNSW) | Approximate nearest neighbour search (cosine similarity) |
| **HuggingFace `datasets`** | Loading the AI arXiv dataset from disk |

### Infrastructure and Cloud

| Technology | Usage |
|------------|-------|
| **Google Cloud Platform (GCP)** | All project infrastructure (project `paw-2026-496213`, region `europe-central2`) |
| **Google Cloud Run** | Serverless microservice hosting (auto-scaling, pay-per-use) |
| **Google Cloud SQL** | Managed PostgreSQL database (DEV + PROD) |
| **Google Artifact Registry** | Docker image registry |
| **Google Cloud Compute Engine** | VM with Elasticsearch for Audit Log |
| **Google Cloud Firestore** | NoSQL document database for product-review-service |
| **Google Cloud Pub/Sub** | Asynchronous inter-service communication (cherry-picked integration) |
| **Google Cloud Monitoring** | Alert policy (5+ errors in 5 minutes → email) |
| **Terraform** | Infrastructure as Code — managing all GCP resources |
| **gcloud CLI** | GCP operations from the command line (deploy, health check, rollback) |

### Containerisation and DevOps

| Technology | Usage |
|------------|-------|
| **Docker** | Containerisation of `product-review-service` and embedding-service |
| **Docker Compose** | Local Qdrant setup with a persistent `qdrant_data` volume |
| **Docker Buildx** | Multi-platform build (`linux/amd64`) with cache in Artifact Registry |
| **Google Cloud Build** | Building Docker images on the GCP side (faster than local) |

### CI/CD and automation

| Technology | Usage |
|------------|-------|
| **GitHub Actions** | Main CI/CD pipeline — build, deploy, tests, auto-PR |
| **gh CLI** | Creating Pull Requests from within the pipeline |
| **Maven** | Build tool for `product-review-service` (Java) |
| **pytest** | API integration tests (Python) |

### Developer tools

| Technology | Usage |
|------------|-------|
| **Git** | Version control, branch management, merge/rebase |
| **GitHub** | Repository hosting, Pull Requests, code review |
| **tqdm** | Progress bar in the embedding script |
| **PowerShell** | Running scripts on Windows (development environment) |

---

## Working on a Shared GitHub Repository

### Branch structure

The project followed the classic **Git Flow** model with two main long-lived branches:

```
main        ← production code, always stable, protected from direct pushes
develop     ← current state of work, where finished features land
```

Every new feature was developed on a dedicated **feature branch** branched off from `develop`:

```
develop
  ├── feat/review-service          (Łukasz — product-review-service)
  ├── feat/reviews                 (Łukasz — monolith integration)
  ├── ci/review-feature-workflow   (Łukasz — CI/CD for reviews)
  ├── feat/pubsub-service-logging  (Szymon — Pub/Sub)
  ├── fixed                        (Łukasz — audit-log + purchase)
  └── docs/vector-db-decisions     (Łukasz — embedding-service docs)
```

### Typical development cycle

```
1. Create a feature branch from develop
   git checkout develop
   git pull origin develop
   git checkout -b feat/my-feature

2. Local work — commits on the feature branch
   git add <files>
   git commit -m "feat(review): describe the change"

3. Push the feature branch to GitHub
   git push origin feat/my-feature

4. Open a Pull Request (develop ← feat/my-feature)
   - code review by other team members
   - GitHub Actions runs automated tests (build + DEV deploy + pytest)
   - after approval — merge to develop

5. After a successful merge to develop:
   - GitHub Actions deploys to DEV environment
   - runs health check on /health
   - automatically creates a PR: main ← develop

6. Merge to main → deploy to PROD
```

### Automation through GitHub Actions

The fully automated pipeline built by Łukasz was a cornerstone of the workflow. On every push to `develop`:

1. A Docker image is built by **Cloud Build** (natively on `linux/amd64`, with cache in Artifact Registry)
2. The image is deployed to **Cloud Run DEV**
3. The pipeline performs a **health check** (`/health`) — waits for a 200 OK response
4. **Integration tests** (`pytest`) are run separately for each entity
5. On success, an automatic **Pull Request** `develop → main` is created
6. After merge to `main` — the same process runs on the **PROD** environment

If a production deployment fails, the `deploy_prod_with_rollback.sh` script automatically restores the previous Cloud Run revision.

### Resolving merge conflicts

With 4 people working in parallel on the same Terraform infrastructure files (`main.tf`), merge conflicts occurred regularly. Typical resolution process:

```bash
# Update the local copy of develop
git fetch origin
git checkout develop
git pull origin develop

# Attempt to merge the feature branch
git checkout feat/my-feature
git merge develop

# On conflict — manually resolve in the editor:
# <<<<<< HEAD (my changes)
# ======
# >>>>>> develop (changes from develop)
# → remove markers, keep the correct content

git add infra/product-review-service/main.tf
git commit -m "merge: resolve conflict in product-review-service main.tf"
git push origin feat/my-feature
```

### Picking up a colleague's work without touching your own changes

When a colleague had a finished feature on a separate branch and you didn't want to risk your own uncommitted changes, **cherry-pick** was used — copying a specific commit onto your own branch:

```bash
# Fetch the colleague's branch locally
git fetch origin feat/pubsub-service-logging

# Check the SHA of the commit you want to bring over
git log origin/feat/pubsub-service-logging --oneline

# Cherry-pick — copy that commit onto your branch
git cherry-pick <SHA>
```

This way the colleague's changes landed on the correct branch without needing to merge the entire branch.

### Commit convention

The project followed the **Conventional Commits** convention:

```
<type>(<scope>): <description>

feat(review): add product-review-service skeleton
fix(infra): remove duplicate Firestore resource blocks
ci(review): add feature branch workflow
docs(embedding-service): add vector DB design decisions
chore: ignore .claude/ directory
merge: resolve conflict in product-review-service main.tf
```

Types: `feat` (new feature), `fix` (bug fix), `ci` (CI/CD), `docs` (documentation), `chore` (housekeeping), `merge` (conflict resolution).
